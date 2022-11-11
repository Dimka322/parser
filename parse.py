import os
import io
import pickle
import shutil
import sys
import tempfile
import warnings
import csv
import requests
import uuid
from requests.exceptions import MissingSchema, ConnectTimeout
from urllib3.exceptions import LocationParseError
from sqlalchemy.exc import IntegrityError
import numpy as np
import psycopg2
from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import login_required, current_user
from keras.utils import load_img
from urllib.parse import urlparse
from selenium import webdriver
from PIL import Image
from bs4 import BeautifulSoup
from werkzeug.routing.exceptions import BuildError

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
from . import db
from .ml_models.nasnet_model import resnet_model
from .ml_models.my_model import model
from .ml_models.detection import CoVAPredict
from project.config.chrome_options import chrome_options
from .models import User, Site, Structure

parse = Blueprint('parse', __name__)

warnings.simplefilter('ignore')
file_extensions = ['.jpg', '.jpeg', '.png', '.pdf', '.txt', '.csv', '.webp', '.mp4', '.mp3']
header = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36'}


def delete_anchors(a_node_str):  # убираем якорные ссылки
    anc_ind = a_node_str.find('#')
    req_ind = a_node_str[anc_ind:].find('?')

    if anc_ind != -1 and req_ind != -1:
        a_node_str = a_node_str[:anc_ind] + a_node_str[req_ind + anc_ind:]
    elif anc_ind != -1:
        a_node_str = a_node_str[:anc_ind]

    return a_node_str


def is_product(url: str):
    result = False
    wd = webdriver.Chrome('project/chromedriver.exe', options=chrome_options)
    try:
        wd.get(url)
    except Exception as e:
        print(e)
        result = False
    else:
        S = lambda X: wd.execute_script('return document.body.parentNode.scroll' + X)
        wd.set_window_size(1920, 1080)  # May need manual adjustment
        data = wd.get_screenshot_as_png()
        img = Image.open(io.BytesIO(data)).resize((331, 331))

        numpy_array = np.asarray(img)[:, :, :3]

    # img_gray = np.dot(numpy_array[..., :3], [0.2989, 0.5870, 0.1140])
    # img_gray = np.reshape(img_gray, [1, 331, 331, 1])
    img_color = np.reshape(numpy_array, [1, 331, 331, 3])

    # prediction_gray = model.predict([img_gray])
    prediction_resnet = resnet_model.predict([img_color])

    color = False

    if prediction_resnet[0][1] > 0.9:
        color = True
    # if prediction_gray[0][1] > 0.9:
    #     gray = True

    if color:
        result = True

    return result, prediction_resnet[0][1]  # , prediction_gray[0][1]


def get_valid_links(domain, amount=0):
    valid_links = []
    structure = []

    links = []
    links_to_visit = []
    try:
        r = requests.get(domain, headers=header)
    except MissingSchema:
        flash('Пустое поле')
        return valid_links, structure

    if r.status_code != 200:
        raise Exception('Это 404')

    soup = BeautifulSoup(r.content)

    a_nodes = soup.findAll("a", href=True)

    for i in a_nodes:
        a_node_str = i['href']

        if a_node_str[
           a_node_str.rfind('.'):].lower() in file_extensions:  # избавляемся от адресов с ненужными расширениями
            continue

        a_node_str = delete_anchors(a_node_str)

        links.append(a_node_str)
        links_to_visit.append(a_node_str)

    links = set(links)  # удаляю дубли
    links = (list(links))

    links_to_visit = set(links_to_visit)  # удаляю дубли
    links_to_visit = (list(links_to_visit))

    parent = 'Главная'
    parent_link = domain
    child_links = links_to_visit.copy()
    [structure.append([parent, parent_link, child_link]) for child_link in child_links]

    while links_to_visit:

        add_to_links_to_visit = []

        for i in links_to_visit:

            link = i
            if len(link) == 0 or 'tel:' in link:
                continue

            if (domain not in link) or ('http' not in link):
                if link[0] != '/':
                    link = '/' + link
                link = domain + link  # Делаем относительную ссылку абсолютной

            try:
                r = requests.get(link, headers=header)
            except LocationParseError as e:
                continue
            except ConnectTimeout:
                continue
            if r.status_code != 200:  # Можно еще подумать над редиректами
                continue

            soup = BeautifulSoup(r.content)
            parent = soup.select('h1')[0].decode_contents()
            parent_link = link

            pred, color = is_product(link)  # Классификация на 2 класса
            if pred:
                print(link)
                valid_links.append(link)
                continue

            if (len(valid_links) >= amount) and (amount > 0):
                return valid_links, structure

            a_nodes = soup.findAll("a", href=True)

            for j in a_nodes:
                a_node_str = j['href']

                if a_node_str[a_node_str.rfind(
                        '.'):].lower() in file_extensions:  # избавляемся от адресов с ненужными расширениями
                    continue

                a_node_str = delete_anchors(a_node_str)  # убираем якорные ссылки

                structure.append([parent, parent_link, a_node_str])

                if a_node_str in links:
                    continue

                links.append(a_node_str)
                add_to_links_to_visit.append(a_node_str)

        links_to_visit = add_to_links_to_visit
    # print(valid_links)
    return valid_links, structure


def detect(link, screen):
    png = CoVAPredict(link, screen)
    return png


@parse.route('/start')
@login_required
def predict():
    return render_template('parse.html', name=current_user.name, email=current_user.email)


@parse.route('/start', methods=['POST'])
@login_required
def predict_post():
    db.session.remove()
    Structure.query.delete()
    url = request.form.get('link')
    domain = urlparse(url).netloc
    screen = str(uuid.uuid4())[:8]
    links, structure = get_valid_links(url, amount=1)
    structure_dict = {}
    for i in structure:
        if structure_dict.get(i[0]):
            structure_dict[i[0]]['CHILDREN'].append(i[2])
        else:
            structure_dict[i[0]] = {'LINK': i[1], 'CHILDREN': [i[2]]}

    print(structure_dict)
    new_structure = Structure(
        domain=domain,
        structure=str(structure_dict)
    )
    try:
        db.session.add(new_structure)
        db.session.commit()
    except IntegrityError:
        return redirect(url_for('result.result_page_user', domain=domain))
    # print(type(structure))
    try:
        return redirect(url_for('result.result_page_user', domain=domain))
    except BuildError:
        flash('Build Error')
        return redirect(url_for('parse.predict'))

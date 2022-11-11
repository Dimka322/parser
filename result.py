import uuid
import ast
from flask import Blueprint, render_template, request, redirect, url_for, send_file, session
from flask_login import current_user, login_required
from .models import User, Site, Structure

result_page = Blueprint('result', __name__)


@result_page.route('/class_result')
@login_required
def result_page_user():
    domain = request.args.get('domain')
    structure = Structure.query.filter_by(domain=domain).first()
    dct = ast.literal_eval(structure.structure)
    # for key in dct:
    # #     print(key)
    # for key in dct.keys():
    #     print(key, request.form[key])
    # for key in dct.keys():
    #     print('children', dct[key]['CHILDREN'])
    return render_template('result.html', dct=dct)


@result_page.route('/result_cova')
@login_required
def result_cova():
    return render_template('result_cova.html', imgname='dba13fb7')

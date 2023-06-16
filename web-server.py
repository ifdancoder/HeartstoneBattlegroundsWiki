import base64
import os
from bson import ObjectId
from flask import Flask, redirect, render_template, request, url_for
from pymongo import MongoClient
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from bson.errors import InvalidId

app = Flask(__name__, template_folder='templates')
app.secret_key = base64.b64encode(os.urandom(24)).decode('utf-8')

client = MongoClient('mongodb://localhost:27017/')
db = client['HeartstoneBattlegrounds']


@app.route('/')
def render_main_page():
    pipeline = [
        {
            '$lookup': {
                'from': 'Types',
                'localField': 'types',
                'foreignField': '_id',
                'as': 'types_data'
            }
        },
        {
            '$unwind': {
                'path': '$types_data',
                'preserveNullAndEmptyArrays': True
            }
        },
        {
            '$group': {
                '_id': '$_id',
                'name': {'$first': '$name'},
                'short_description': {'$first': '$short_description'},
                'small_image_url': {'$first': '$small_image_url'},
                'type_ids': {'$push': '$types_data._id'},
                'type_names': {'$push': '$types_data.name'},
                'type_small_image_urls': {'$push': '$types_data.small_image_url'}
            }
        },
        {
            '$project': {
                '_id': 1,
                'name': 1,
                'short_description': 1,
                'small_image_url': 1,
                'type_ids': 1,
                'type_names': 1,
                'type_small_image_urls': 1
            }
        }
    ]
    minions = []
    for i, dct in enumerate(db.Minions.aggregate(pipeline)):
        dct['number'] = i + 1
        dct['types'] = zip(dct['type_small_image_urls'], dct['type_names'], dct['type_ids'])
        del dct['type_ids']
        del dct['type_names']
        minions.append(dct)
    if minions:
        return render_template('main_page.html', minions=minions)

def is_objectid(s):
    try:
        ObjectId(str(s))
        return True
    except InvalidId:
        return False

@app.route('/type/<string:mongo_id>')
def render_type(mongo_id):
    if is_objectid(mongo_id):
        type_db = db.Types.find_one({'_id': ObjectId(mongo_id)})
        if type_db:
            type_db['description'] = type_db['description'].split('\\n')
            if 'bibliography' in type_db:
                try:
                    type_db['bibliography'] = get_bibliography(type_db['bibliography'])
                except:
                    del type_db['bibliography']
            return render_template('type.html', type_db=type_db)
    return render_template('does_not_exist.html', name='типа')

@app.route('/object/<string:mongo_id>')
def render_object(mongo_id):
    if is_objectid(mongo_id):
        object_db = db.Minions.find_one({'_id': ObjectId(mongo_id)})
        if object_db:
            object_db['long_description'] = object_db['long_description'].split('\\n')
            if 'bibliography' in object_db:
                try:
                    object_db['bibliography'] = get_bibliography(object_db['bibliography'])
                except:
                    del object_db['bibliography']
            return render_template('object.html', object_db=object_db)
    return render_template('does_not_exist.html', name='существа')



@app.route('/create_minion', methods=['POST', 'GET'])
def render_create_minion():
    if request.method == 'POST':
        minion_name_error = False
        minion_description_error = False
        minion_image_error = False
        minion_card_image_error = False
        object_types_error = False

        image = request.files['minion_image']
        card_image = request.files['minion_card_image']
        image_filename = image.filename
        small_img_url = os.path.join('img/object/', image_filename)
        image_path = os.path.join(app.root_path, 'static', small_img_url)
        card_image_filename = card_image.filename
        big_img_url = os.path.join(
            'img/object/small/', card_image_filename)
        card_image_path = os.path.join(app.root_path, 'static', big_img_url)

        while(Path(image_path).exists()):
            splitted = image_path.split('.')
            image_path = splitted[0] + 't.' + splitted[1]

        while(Path(card_image_path).exists()):
            splitted = card_image_path.split('.')
            card_image_path = splitted[0] + 't.' + splitted[1]

        if not any((image_filename.endswith('.png'), image_filename.endswith('.jpg'), image_filename.endswith('.jpeg'))):
            minion_image_error = 'Неверный формат изображения'

        if not any((card_image_filename.endswith('.png'), card_image_filename.endswith('.jpg'), card_image_filename.endswith('.jpeg'))):
            minion_card_image_error = 'Неверный формат изображения'

        name = request.form['minion_name']
        long_description = request.form['minion_description']

        if len(long_description) < 5 or len(long_description) > 300 and long_description.count('.') < 2:
            minion_description_error = 'Описание должно быть от 5 до 300 символов и состоять как минимум из 2-х предложений'

        short_description = long_description.split('.')[0] + '.'
        types = [ObjectId(typeid) for typeid in request.form.getlist('object_types')]

        if any((minion_name_error, minion_description_error, minion_image_error, minion_card_image_error, object_types_error)):
            type_db = list(db.Types.find())
            return render_template('create_minion.html', type_db=type_db, minion_name_error=minion_name_error, minion_description_error=minion_description_error, minion_image_error=minion_image_error, minion_card_image_error=minion_card_image_error, object_types_error=object_types_error, name=name, long_description=long_description, types=types)

        image.save(image_path)
        card_image.save(card_image_path)
        db.Minions.insert_one({
            'name': name,
            'short_description': short_description,
            'long_description': long_description,
            'types': types,
            'small_image_url': small_img_url,
            'big_image_url': big_img_url
        })
        return redirect(url_for('render_main_page'))
    type_db = list(db.Types.find())
    return render_template('create_minion.html', type_db=type_db)


def get_bibliography(bibliography):
    tmp_bibliography = []
    for link in bibliography:
        response = requests.get(link)
        soup = BeautifulSoup(response.content, 'html.parser')
        title = soup.find('title').get_text()
        title_text = title if title != '' else link
        tmp_bibliography.append((link, title_text))
    return tmp_bibliography


if __name__ == '__main__':
    app.run(port=80)

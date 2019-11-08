import os
from flask import Flask, redirect, url_for, request, jsonify, render_template
from pymongo import MongoClient
import sys
import uuid
from datetime import datetime

app = Flask(__name__)
client = MongoClient('127.0.0.1', 27017)
db = client.nrs

@app.route('/list_devices')
def list_devices():
    _items = db.devices.find()
    items = []
    for item in _items:
        if 'state' in item:
            person = db.persons.find_one({'_id':item['state']['person']})
            if person == None:
                return {"state": "error", "msg": "Device listed and borrowed by unexisting person"}
            item['state']['person_name'] = person['name']
            item['state']['person_place'] = person['place']
        items.append(item)

    return jsonify(items)


@app.route('/enlist_person', methods=['POST'])
def enlist_person():

    item_doc = {
        '_id': str(uuid.uuid4()),
        'id': request.form['id'],
        'name': request.form['name'],
        'place': request.form['place'],
        'codes_nfc': [request.form['code_nfc']]
    }
    db.persons.insert_one(item_doc)

    db.newnfcs.remove({'_id':request.form['code_nfc']})
    return jsonify({"state":"ok"})

@app.route('/delete_person', methods=['POST'])
def delete_person():

    person_id = request.form['person_id']
    person = db.persons.find_one({'_id':person_id})
    if not person:
        return jsonify({'state':'error', 'msg':'person does not exist'})

    db.persons.remove({'_id':person_id})
    db.devices.update_many({'state':{'$exists':True}, 'state.person': person_id}, {'$unset':{'state':True}})
    return jsonify({"state":"ok"})

@app.route('/create_device', methods=['POST'])
def create_device():

    item_doc = {
        '_id': str(uuid.uuid4()),
        'name': request.form['name'],
        'os_version': request.form['os_version'],
        'code_nfc': request.form['code_nfc'],
        'tags': request.form['tags']
    }
    db.devices.insert_one(item_doc)

    db.newnfcs.remove({'_id':request.form['code_nfc']})

    return jsonify({"state":"ok"})

@app.route('/delete_device', methods=['POST'])
def delete_device():

    device_id = request.form['device_id']
    device = db.devices.find_one({'_id':device_id})
    if not device:
        return jsonify({'state':'error', 'msg':'device does not exist'})

    db.devices.remove({'_id':device_id})
    return jsonify({"state":"ok"})

@app.route('/identify', methods=['POST'])
def identify():

    code_nfc = request.form['code']

    person = db.persons.find_one({'codes_nfc':{'$elemMatch':{'$eq':code_nfc}}})
    device = db.devices.find_one({'code_nfc':code_nfc})

    if person:
        return jsonify({"type":"person"})

    if device:
        return jsonify({"type":"device"})

    return jsonify({"type":"unknown"})

@app.route('/acquire', methods=['POST'])
def acquire():

    person_nfc = request.form['person_nfc']
    device_nfc = request.form['device_nfc']

    person = db.persons.find_one({'codes_nfc':{'$elemMatch':{'$eq':person_nfc}}})
    device = db.devices.find_one({'code_nfc':device_nfc})

    if person == None or device == None:
        return jsonify({"state":"error", "msg":"Device or person not found"})

    state = {
        'person': person['_id'],
        'ts_borrow': datetime.timestamp(datetime.now())
    }

    db.devices.update_one({'_id': device['_id']},{'$set':{'state':state}})

    return jsonify({"state":"ok"})

@app.route('/release', methods=['POST'])
def release():

    device_nfc = request.form['device_nfc']

    device = db.devices.find_one({'code_nfc':device_nfc})

    if device == None:
        return jsonify({"state":"error", "msg":"device not found"})

    if not 'state' in device:
        return jsonify({"state":"error", "msg":"device is not borrowed"})

    db.devices.update_one({'_id': device['_id']},{'$unset':{'state':1}})

    return jsonify({"state":"ok"})


@app.route('/new_nfc_code', methods=['POST'])
def new_nfc_code():

    code_nfc = request.form['code']

    person = db.persons.find_one({'codes_nfc':{'$elemMatch':{'$eq':code_nfc}}})
    device = db.devices.find_one({'code_nfc':code_nfc})

    if person or device:
        return jsonify({"state":"error", "msg":"nfc code is already enlisted"})

    new_nfc = db.newnfcs.find_one({'_id':code_nfc})
    if new_nfc:
        return jsonify({"state":"error", "msg":"new nfc already stored"})

    db.newnfcs.insert({'_id':code_nfc, 'ts':datetime.timestamp(datetime.now())})

    return jsonify({"state":"ok"})

@app.route('/get_new_nfc_code', methods=['GET'])
def get_new_nfc_code():
    _new_nfcs = db.newnfcs.find()
    new_nfcs = [item for item in _new_nfcs]

    return jsonify(new_nfcs)

@app.route('/', methods=['GET'])
def front_page():
    _devices = db.devices.find()
    devices = [item for item in _devices]
    _persons = db.persons.find()
    persons = {item['_id']: item for item in _persons}

    _new_nfcs = db.newnfcs.find()
    new_nfcs = [item for item in _new_nfcs]

    return render_template('front.html', devices=devices, persons=persons, new_nfcs=new_nfcs)

@app.route('/admin_page', methods=['GET'])
def admin_page():
    _new_nfcs = db.newnfcs.find()
    new_nfcs = [item for item in _new_nfcs]

    return render_template('admin.html', new_nfcs=new_nfcs)

@app.template_filter('dt')
def _jinja2_filter_datetime(date, fmt=None):
    date = datetime.fromtimestamp(date)
    if fmt:
        return date.strftime(fmt)
    else:
        return date.strftime('%m/%d/%Y %H:%M:%S')

if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True)
    #socketio.run(app, debug=True)

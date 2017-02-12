from tinydb import TinyDB , Query
from botocore.exceptions import ClientError
from facepy import GraphAPI
from Main import FaceDatabase
import json

with open('creds', "r") as f:
	data = json.load(f)

graph = GraphAPI(data['facebook'])

db = TinyDB('facebook.json')
facedb = FaceDatabase('creds', table='skynetdb', collection='Skynet', bucket='skynetdb')

query_item = Query()

for person in db.all():
	if 	'pic' not in person:
		print "Getting data for {} ({})".format(person['name'].encode('utf-8'), person['id'].encode('utf-8'))
		pic = graph.get('/{}/picture'.format(person['id']), type='large')
		try:
			person_data = {'First Name': person['name'].split()[0].encode('utf-8'),
						   'Last Name': person['name'].split()[1].encode('utf-8')}
		except IndexError:
			person_data = {'First Name': person['name'].encode('utf-8'),
						   'Last Name': None}
		try:
			facedb.add_face(pic, person_data)
			db.update({'pic': True}, query_item.id == person['id'])
		except FaceDatabase.FaceDatabaseException, e:
			print "Error: {} for {} ({})".format(e, person['name'].encode('utf-8'), person['id'].encode('utf-8'))
			if 'already has a picture in skynetdb' not in str(e):
				db.update({'pic': False}, query_item.id == person['id'])
			else:
				db.update({'pic': True}, query_item.id == person['id'])


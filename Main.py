from boto3.dynamodb.conditions import Key
from boto3.dynamodb import types
import logging.handlers
import numpy as np
import logging
import decimal
import boto3
import json
import cv2

logger = logging.getLogger(__name__)


def decimal_default(obj):
	if isinstance(obj, decimal.Decimal):
		return float(obj)
	raise TypeError


class FaceDatabase:
	class FaceDatabaseException(Exception):
		pass

	def __init__(self, keyfile, table=None, collection=None, bucket=None):
		with open(keyfile, "r") as f:
			data = json.load(f)
			self.ACCESS_KEY = data['access_key_id']
			self.SECRET_KEY = data['secret_access_key']
		self.dynamodb = boto3.resource(
			'dynamodb',
			region_name="us-east-1",
			aws_access_key_id=self.ACCESS_KEY,
			aws_secret_access_key=self.SECRET_KEY
		)
		self.S3 = boto3.resource(
			's3',
			region_name="us-east-1",
			aws_access_key_id=self.ACCESS_KEY,
			aws_secret_access_key=self.SECRET_KEY
		)
		self.rek = boto3.client(
			'rekognition',
			region_name="us-east-1",
			aws_access_key_id=self.ACCESS_KEY,
			aws_secret_access_key=self.SECRET_KEY
		)
		# Getters and setters because table is a reference to dynamodb.Table
		if table is not None:
			self.table = self.dynamodb.Table(table)
		else:
			self.table = None

		# Getters and setters because table is a reference to S3.Bucket
		if bucket is not None:
			self.bucket = self.S3.Bucket(bucket)
		else:
			self.bucket = bucket

		# No getters and setters cus this is just used as a string
		if collection is not None:
			self.collection = collection
		else:
			self.collection = None

	@property
	def table(self):
		if self.table is not None:
			return self.table.table_name
		else:
			return None

	@table.setter
	def table(self, db):
		logger.debug('Set table to {}'.format(db))
		if db is not None:
			self.table = self.dynamodb.Table(db)
		else:
			self.table = None

	@property
	def bucket(self):
		return self.bucket.name

	@bucket.setter
	def bucket(self, value):
		if value is not None:
			self.bucket = self.S3.Bucket(value)
		else:
			self.bucket = None

	def dump_coll(self):
		self.rek.delete_collection(
			CollectionId=self.collection
		)

		self.rek.create_collection(
			CollectionId=self.collection
		)

	def add_face(self, image_data, person_data):
		"""Adds the largest face in image to the current dynoDB Table"""
		faces = self.rek.index_faces(
			CollectionId=self.collection,
			Image={
				'Bytes': image_data
			}
		)

		if len(faces['FaceRecords']) == 0:
			raise self.FaceDatabaseException("Found 0 faces in image!")

		faceid = faces['FaceRecords'][0]['Face']['FaceId']
		facedata = faces['FaceRecords'][0]
		if self.table.query(
				KeyConditionExpression=Key('FaceId').eq(faceid)
		)['Count'] > 0:
			logger.debug("Raised Exception: {} already has a picture in {}!".format(faceid, self.table.table_name))
			raise self.FaceDatabaseException("{} already has a picture in {}!".format(faceid, self.table.table_name))
		logger.debug("{} is not in {} uploading".format(faceid, self.table.table_name))
		self.table.put_item(
			Item={
				'FaceId': faceid,
				'PersonData': person_data,
			}
		)
		cropped_image = self.markup_image(image_data, facedata, crop=True)
		self.bucket.put_object(Key='{}.jpg'.format(faceid), Body=cropped_image)

		return {'FaceID': faceid, 'FaceData': facedata}

	def identify_face(self, image_data):
		faces = self.rek.index_faces(
			CollectionId=self.collection,
			Image={
				'Bytes': image_data
			}
		)
		query = list()
		for item in faces['FaceRecords']:
			ret = self.table.query(KeyConditionExpression=Key('FaceId').eq(item['Face']['FaceId']))
			if ret['Count'] == 1:
				query.append(ret['Items'][0])
			else:
				query.append(None)
		return zip(faces['FaceRecords'], query)

	@staticmethod
	def markup_image(image_data, facedata, crop=False, rawCV=False):
		if not rawCV:
			image_data = np.fromstring(image_data, dtype='uint8')
			opencv_image = cv2.imdecode(image_data, cv2.IMREAD_UNCHANGED)
		else:
			opencv_image = image_data
		if len(opencv_image.shape) != 3:
			print "WTF!"
			exit()
		height, width, channels = opencv_image.shape
		bounding_box = {
			# Width, Height, left and top in pixels
			'Width': facedata['FaceDetail']['BoundingBox']['Width'] * width,
			'Height': facedata['FaceDetail']['BoundingBox']['Height'] * height,
			'Top': facedata['FaceDetail']['BoundingBox']['Top'] * height,
			'Left': facedata['FaceDetail']['BoundingBox']['Left'] * width
		}
		if crop:
			opencv_image = opencv_image[max(int(bounding_box['Top'] - bounding_box['Height']), 0):max(int(bounding_box['Top'] + bounding_box['Height'] * 2), 0),
							max(int(bounding_box['Left'] - bounding_box['Width']), 0):max(int(bounding_box['Left'] + bounding_box['Width'] * 2), 0)]
		else:
			cv2.rectangle(opencv_image,
						(int(bounding_box['Left']), int(bounding_box['Top'])),
						(int(bounding_box['Left'] + bounding_box['Width']), int(bounding_box['Top'] + bounding_box['Height'])),
						(0, 255, 255), 2)
		if rawCV:
			return opencv_image
		return cv2.imencode('.jpg', opencv_image)[1].tostring()

	@staticmethod
	def float_to_decimal(item):
		"""Method to convert all float elements in nested dict and list object to float"""
		for key in item:
			if isinstance(item[key], list):
				tmp = list()
				for i in item[key]:
					if isinstance(i, dict):
						tmp.append(FaceDatabase.float_to_decimal(i))
					elif isinstance(i, float):
						tmp.append(types.Decimal(i))
				item[key] = tmp
			if isinstance(item[key], dict):
				item[key] = FaceDatabase.float_to_decimal(item[key])
			if isinstance(item[key], float):
				item[key] = types.Decimal(item[key])
		return item


if __name__ == "__main__":
	facedb = FaceDatabase('creds', table='skynetdb', collection='Skynet', bucket='skynetdb')
	photo = "james.jpg"
	with open(photo, "rb") as f:
		photo_data = f.read()
	try:
		with open('out.jpg', 'wb') as f:
			f.write(facedb.markup_image(photo_data, facedb.add_face(photo_data, {'First Name': 'Mark', 'Last Name': 'Omo'})['FaceData']))
	except FaceDatabase.FaceDatabaseException:
		print "That person is already in the database!"

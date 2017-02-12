from PIL import Image, ImageTk
import threading
import thread
import time
import Tkinter
import time
import cv2
import Skynet
import numpy as np
import math
import sys
import os

def clamp_aspect(ratio, width, height):
	width = float(width)
	height = float(height)
	if width > height * ratio:
		width = height * ratio
	elif height > width / ratio:
		height = width / ratio
	width = int(math.ceil(width))
	height = int(math.ceil(height))
	return width, height

def resize_to_height(img, height):
	ratio = float(height) / float(img.shape[0])
	width = int(math.ceil(float(img.shape[1]) * ratio))
	return cv2.resize(img, (width, height))

def centered_clamp_width(img, width):
	offset = img.shape[1] - width
	if not offset > 0:
		return img
	offset_a = offset//2
	offset_b = offset_a
	if offset % 2:
		offset_b += 1
	return img[:, offset_a:(img.shape[1]-offset_b)]

def threaded_rescale(frame_in, frame_out, tr_control, tr_lock, instance_id):
	tr_lock.acquire()
	while not tr_control["stop"]:
		if len(frame_in) and frame_in[tr_control['ci']] is not None and not tr_control['ready']:
			frame = frame_in[tr_control['ci']]
			tr_control['ready'] = True
			print "ID"+str(instance_id)+" got ci "+str(tr_control['ci'])
			size = clamp_aspect(16.0/9.0, tr_control["width"], tr_control["height"])
			tr_lock.release()
			frame = cv2.resize(frame, size)
			frame = Image.fromarray(frame)
			frame = ImageTk.PhotoImage(frame)
			tr_lock.acquire()
			frame_out[0]=frame
			tr_control['done']=False
		else:
			tr_lock.release()
			tr_lock.acquire()

class object_tail:
	def __init__(self, frame, point):
		self.locs = [point]
		self.face_id = None
		self.face_data = {}
		self.face_callback = None
		self.rek_req_active = False
		self.last_time = 0

	def __eq__(self, other):
		if other is None:
			return False
		return other.locs == self.locs

	def dist(self, point):
		return math.sqrt((point[1]-self.locs[-1][1])**2 + (point[0]-self.locs[-1][0])**2)

	def add(self, point):
		self.locs.append(point)

	def plot_tail(self, img, col):
		x, y, w, h = self.locs[-1]
		cv2.rectangle(img, (x, y), (x + w, y + h), col, 2)
		if len(self.face_data):
			text_name = self.face_data["First Name"]+" "+self.face_data["Last Name"]
			cv2.putText(img, text_name, (x,y+h+24), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
	
	def rekognize(self, img, facedb, callback=None):
		self.face_callback = callback
		x, y, w, h = self.locs[-1]
		if w < 80 or h < 80:
			return False
		self.rek_req_active = True
		x1 = x - (w/2)
		x2 = x + ((3*w)/2)
		y1 = y - (h/2)
		y2 = y + ((3*h)/2)
		x1=max(x1, 0)
		y1=max(y1, 0)
		x2=min(x2, img.shape[1])
		y2=min(y2, img.shape[0])
		opencv_image = img[y1:y2, x1:x2]
		t = threading.Thread(target=t_rekognize, args=(opencv_image, facedb, self.c_rekognize))
		t.daemon = True
		t.start()
	
	def c_rekognize(self, result):
		self.rek_req_active = False
		if len(result)!=3:
			print "Error: Bad data"
			return False
		if result[1] is None:
			return False
		self.face_id = result[1]["FaceId"]
		self.face_data = result[1]["PersonData"]
		self.last_time = time.time()
		if self.face_callback is not None:
			self.face_callback(self, result)

def t_rekognize(img, facedb, callback):
	enc_jpeg = cv2.imencode('.jpg', img)[1].tostring()
	result = facedb.identify_face(enc_jpeg, 0.85)
	callback(result)

class simpleapp_tk:
	def __init__(self):
		self.root=Tkinter.Tk()
		self.root.title("Skynet Watches")
		self.root.state("zoomed")
		self.root.focus_set()
		self.root.wm_iconbitmap(bitmap = "mia.ico")
		
		self.root.configure(bg="#555")
		self.cframe = Tkinter.Frame(self.root, bg="#555", width=200)
		self.cframe.pack(fill=Tkinter.Y, padx=10, side=Tkinter.LEFT)
		self.cframe.pack_propagate(0)
		
		self.vframe = Tkinter.Label(self.root, bd=0, bg='#222')
		self.vframe.pack(fill="both", expand=True)
		
		self.facedb = Skynet.FaceDatabase('creds', table='skynetdb', collection='Skynet', bucket='skynetdb')
		self.face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
		self.cfaces = {}
		
		self.tr_control = {
				'stop':False,
				'ready':False,
				'done':False,
				'width':100,
				'height':100,
				'ci':0,
				'buf_size':8,
				'show_frame':self.show_frame
			}
		#self.tr_lock = threading.Lock()
		self.tr_iframe = {}
		self.tr_oframe = [None]
		self.tracked_faces = []
		
		#Camera
		self.width, self.height = 1280, 720
		self.cap = cv2.VideoCapture(1)
		time.sleep(3)
		self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
		self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
		self.get_frame()
		#self.show_frame()
		
		#thread.start_new_thread(threaded_rescale, (self.tr_iframe, self.tr_oframe, self.tr_control, self.tr_lock, 1))
		#thread.start_new_thread(threaded_rescale, (self.tr_iframe, self.tr_oframe, self.tr_control, self.tr_lock, 2))
		#thread.start_new_thread(threaded_rescale, (self.tr_iframe, self.tr_oframe, self.tr_control, self.tr_lock, 3))
		#thread.start_new_thread(threaded_rescale, (self.tr_iframe, self.tr_oframe, self.tr_control, self.tr_lock, 4))
		#threading.Thread.__init__(self)
	
	def get_frame(self):
		_, frame = self.cap.read()
		frame = cv2.flip(frame, 1)
		
		gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
		faces = list(self.face_cascade.detectMultiScale(gray, 1.3, 5))
		faces = [list(x) for x in faces]
		if len(self.tracked_faces) == 0 or len(faces) == 0:
			self.tracked_faces = []
			for item in faces:
				inter = object_tail(frame, item)
				inter.rekognize(frame[:, :], self.facedb, self.pf_inter)
				self.tracked_faces.append(inter)
		else:
			try:
				self.tracked_faces = [x for x in self.tracked_faces if (min([x.dist(y) for y in faces]) < 45)]
			except ValueError, e:
				print e
				print faces
				raise
			for tracker in self.tracked_faces:
					tracker.counter = 0
					index = [tracker.dist(x) for x in faces].index(min([tracker.dist(x) for x in faces]))
					tracker.add(faces[index])
					faces.remove(faces[index])
			for point in faces:
				inter = object_tail(frame, point)
				inter.rekognize(frame[:, :], self.facedb, self.pf_inter)
				self.tracked_faces.append(inter)
		current_faceids = []
		for face in self.tracked_faces:
			if face.face_id is not None:
				current_faceids.append(face.face_id)
			elif not face.rek_req_active and face.last_time < time.time():
				face.rekognize(frame[:, :], self.facedb, self.pf_inter)
		for faceid in self.cfaces:
			if not faceid in current_faceids and not self.cfaces[faceid]['hidden'] and not self.cfaces[faceid]['pop_timeout']:
				self.cfaces[faceid]["pop_timeout"] = self.root.after(5000, self.pop_face, (faceid))
		for faceid in current_faceids:
			if not faceid in self.cfaces or self.cfaces[faceid]['hidden']:
				self.push_face(faceid)
		
		col = 0
		for item in self.tracked_faces:
			item.plot_tail(frame, (255-col, col, 255))
			col += 255/3
		
		frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)
		size = clamp_aspect(16.0/9.0, self.vframe.winfo_width(), self.vframe.winfo_height())
		frame = cv2.resize(frame, size)
		frame = Image.fromarray(frame)
		frame = ImageTk.PhotoImage(frame)
		self.vframe.configure(image=frame)
		self.vframe.image=frame
		'''
		self.tr_lock.acquire()
		self.tr_control['width'] = self.vframe.winfo_width()
		self.tr_control['height'] = self.vframe.winfo_height()
		next_index = self.tr_control['ci'] + 1
		if next_index >= self.tr_control['buf_size']:
			next_index = 0
		self.tr_iframe[next_index] = frame
		self.tr_control['ci'] = next_index
		self.tr_control['ready'] = False
		self.tr_lock.release()
		'''
		self.root.after(10, self.get_frame)
	
	def show_frame(self):
		self.tr_lock.acquire()
		if self.tr_oframe[0] is not None and not self.tr_control['done']:
			myframe = self.tr_oframe[0]
			self.tr_control['done']=True
			self.tr_lock.release()
			self.tr_lock.acquire()
		if not self.tr_control['stop']:
			self.root.after(10, self.show_frame)
		self.tr_lock.release()
	
	def pf_inter(self, tail, result):
		if len(tail.face_data) > 0:
			self.push_face(tail.face_id, "Confidence: "+"{0:.2f}".format(result[2])+"%")
	
	def push_face(self, faceid, addtl_label=False):
		if faceid in self.cfaces:
			if self.cfaces[faceid]['pop_timeout']:
				self.root.after_cancel(self.cfaces[faceid]["pop_timeout"])
				self.cfaces[faceid]["pop_timeout"] = False
			if self.cfaces[faceid]['ready'] and addtl_label != False:
				self.cfaces[faceid]["ui_extra"].config(text=addtl_label)
				self.cfaces[faceid]['addtl_label']=addtl_label
			if self.cfaces[faceid]['hidden']:
				self.cfaces[faceid]["ui_spacer"].pack(anchor=Tkinter.N)
				self.cfaces[faceid]["ui_pic"].pack(anchor=Tkinter.N, fill=Tkinter.X)
				self.cfaces[faceid]["ui_text"].pack(anchor=Tkinter.N, fill=Tkinter.X)
				if addtl_label != False or self.cfaces[faceid]['addtl_label'] != False:
					self.cfaces[faceid]["ui_extra"].pack(anchor=Tkinter.N, fill=Tkinter.X)
				self.cfaces[faceid]['hidden'] = False
			return
		self.cfaces[faceid] = {'ready':False,'hidden':False, 'pop_timeout':False, 'addtl_label':False}
		self.cfaces[faceid]["db_image"], self.cfaces[faceid]["db_data"] = self.facedb.get_by_faceid(faceid)
		self.cfaces[faceid]["ui_spacer"] = Tkinter.Frame(self.cframe, bg="#555", width=200, height=16)
		self.cfaces[faceid]["ui_spacer"].pack(anchor=Tkinter.N)
		self.cfaces[faceid]["ui_spacer"].pack_propagate(0)
		
		self.cfaces[faceid]["ui_pic"] = Tkinter.Label(self.cframe, bg="#444", bd=0)
		self.cfaces[faceid]["ui_pic"].pack(anchor=Tkinter.N, fill=Tkinter.X)
		image_data = np.fromstring(self.cfaces[faceid]["db_image"], dtype='uint8')
		opencv_image = cv2.imdecode(image_data, cv2.IMREAD_UNCHANGED)
		opencv_image = cv2.cvtColor(opencv_image, cv2.COLOR_BGR2RGB)
		opencv_image = resize_to_height(opencv_image, 150)
		opencv_image = centered_clamp_width(opencv_image, 200)
		frame = Image.fromarray(opencv_image)
		image = ImageTk.PhotoImage(frame)
		self.cfaces[faceid]["ui_pic"].configure(image=image)
		self.cfaces[faceid]["ui_pic"].image = image
		
		self.cfaces[faceid]["ui_text"] = Tkinter.Label(self.cframe, font=("Trebuchet MS", 16), bg="#444", fg="#FFF")
		new_text = self.cfaces[faceid]["db_data"]["First Name"]+" "+self.cfaces[faceid]["db_data"]["Last Name"]
		print new_text
		self.cfaces[faceid]["ui_text"].config(text=new_text)
		self.cfaces[faceid]["ui_text"].pack(anchor=Tkinter.N, fill=Tkinter.X)
		
		self.cfaces[faceid]["ui_extra"] = Tkinter.Label(self.cframe, font=("Trebuchet MS", 11), bg="#444", fg="#FEFEFE")
		extra_text = False
		if addtl_label != False:
			extra_text = addtl_label
			self.cfaces[faceid]['addtl_label']=addtl_label
		elif self.cfaces[faceid]['addtl_label'] != False:
			extra_text = self.cfaces[faceid]['addtl_label']
		if extra_text:
			self.cfaces[faceid]["ui_extra"].config(text=extra_text)
			self.cfaces[faceid]["ui_extra"].pack(anchor=Tkinter.N, fill=Tkinter.X)
		
		self.cfaces[faceid]['ready']=True
	
	def pop_face(self, faceid):
		if not faceid in self.cfaces:
			return
		try:
			self.cfaces[faceid]["ui_spacer"].pack_forget()
			self.cfaces[faceid]["ui_pic"].pack_forget()
			self.cfaces[faceid]["ui_text"].pack_forget()
			self.cfaces[faceid]["ui_extra"].pack_forget()
			self.cfaces[faceid]['hidden'] = True
		except KeyError, e:
			print e
			print self.cfaces[faceid]
			raise
	
	def end_it_all(self):
		while len([face for face in self.tracked_faces if face.rek_req_active]):
			time.sleep(10)
		print "Bye!"
		self.cap.release()
		self.root.destroy()
		os._exit(0)
	
	def run(self):
		self.root.protocol("WM_DELETE_WINDOW", self.end_it_all)
		self.root.mainloop()

if __name__ == "__main__":
	app = simpleapp_tk()
	app.run()
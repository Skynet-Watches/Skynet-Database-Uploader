from Skynet import FaceDatabase
from PIL import Image, ImageTk
import threading
import Tkinter
import json
import cv2

class simpleapp_tk(threading.Thread):
	def __init__(self):
		self.root=Tkinter.Tk()
		self.root.title("DFAC Quick Panel")

		self.facedb = FaceDatabase('creds', table='skynetdb', collection='Skynet', bucket='skynetdb')

		# Camera
		self.Cam_frame = None
		self.width, self.height = 800, 600
		self.cap = cv2.VideoCapture(0)

		# Input label
		self.first_name_label = Tkinter.Label(self.root, text="First Name:",
											font=("Courier", 30))
		self.first_name_label.grid(row=1, column=0, sticky='w',
									columnspan=2)
		self.first_name_entry = Tkinter.Entry(self.root, font=("Courier", 20))
		self.first_name_entry.grid(row=2, column=0, sticky='wens', columnspan=2)
		self.last_name_label = Tkinter.Label(self.root, text="First Name:",
											  font=("Courier", 30))
		self.last_name_label.grid(row=3, column=0, sticky='w', columnspan=2)
		self.last_name_entry = Tkinter.Entry(self.root, font=("Courier", 20))
		self.last_name_entry.grid(row=4, column=0, sticky='wens', columnspan=2)

		# Entry button
		self.entry_buttion = Tkinter.Button(self.root, text="Capture",
										font=("Courier", 30),
										command=self.capture_image)
		self.entry_buttion.grid(row=5, column=0, sticky='wens')

		self.submit_buttion = Tkinter.Button(self.root, text="Submit",
										font=("Courier", 30),
										state='disabled',
										command=self.submit)
		self.submit_buttion.grid(row=5, column=1, sticky='wens')

		self.resume_buttion = Tkinter.Button(self.root, text="Reset",
										 font=("Courier", 30),
										 command=self.reset)
		self.resume_buttion.grid(row=6, column=0, sticky='wens', columnspan=2)

		self.markup = None
		self.submit_frame = None

		self.show_frame()
		threading.Thread.__init__(self)

	def submit(self):
		try:
			print self.facedb.add_face(self.submit_frame,
							{'First Name':self.first_name_entry.get(),
							'Last Name':self.last_name_entry.get()})
		except FaceDatabase.FaceDatabaseException, e:
			print e
		self.markup = None
		self.submit_buttion.config(state="disabled")

	def reset(self):
		self.markup = None
		self.submit_buttion.config(state="disabled")

	def capture_image(self):
		_, frame = self.cap.read()
		rawframe = cv2.flip(frame, 1)
		old = rawframe
		frame = cv2.imencode('.jpg', rawframe)[1].tostring()
		self.submit_frame = frame
		id = self.facedb.identify_face(frame)
		print json.dumps(id, indent=4)
		rawframe = self.facedb.markup_image(rawframe, id[0], rawCV=True, id=True)
		rawframe = cv2.cvtColor(rawframe, cv2.COLOR_BGR2RGB)
		frame = Image.fromarray(rawframe)
		frame = ImageTk.PhotoImage(frame)
		self.markup = frame
		self.submit_buttion.config(state="normal")

	def show_frame(self):
		if self.markup is None:
			_, frame = self.cap.read()
			frame = cv2.flip(frame, 1)
			frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
			frame = Image.fromarray(frame)
			frame = ImageTk.PhotoImage(frame)
		else:
			frame = self.markup
		if self.Cam_frame is None:
			self.Cam_frame = Tkinter.Label(image=frame)
			self.Cam_frame.image = frame
			self.Cam_frame.grid(row=0, column=0, columnspan=2)
		else:
			self.Cam_frame.configure(image=frame)
			self.Cam_frame.image = frame
		self.root.after(10, self.show_frame)

	def run(self):
		self.root.mainloop()

if __name__ == "__main__":
	app = simpleapp_tk()
	app.start()

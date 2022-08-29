from PyQt5 import QtWidgets
from PyQt5.QtWidgets import *
from PyQt5.QtCore import QTimer,QUrl,Qt
from PyQt5.QtGui import QIcon,QDesktopServices,QPixmap,QCursor,QPixmap
from gui import Ui_MainWindow
import mqttClient
import sys

class wincore (QtWidgets.QMainWindow,Ui_MainWindow):
    def __init__(self):
        super(wincore,self).__init__()
        self.setupUi(self)
        self.init()

    def init(self):
        self.statusBar=QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage('客户端初始化-------',5000) 
        self.setWindowTitle('人脸识别客户端')
        
        self.pushButton.clicked.connect(self.buttonStart)
        self.pushButton_2.clicked.connect(self.buttonStop)
        
        #禁止窗口大小改变
        self.setFixedSize(self.width(), self.height())
        # 线程
        self.mqttNet = mqttClient.mqttClientFace()
        self.mqttNet.start() 
        self.mqttNet.setCallback(self.netChange,self.inferCallbakc)
        
    def closeEvent(self,event):
        self.mqttNet.close()

    def buttonStart(self):
        self.pushButton.setEnabled(False)
        self.mqttNet.go()

    def buttonStop(self):
        self.pushButton.setEnabled(True)
        self.label_5.setPixmap(QPixmap(""))
        self.mqttNet.suspend()

    def inferCallbakc(self,taskId,img,res):
        self.label_2.setText(taskId)
        self.label_4.setText(res)
        pixmap = QPixmap(img)
        self.label_5.setScaledContents(True)
        self.label_5.setPixmap(pixmap)

    def netChange(self,status):
        print(status)


def startGui():
    app= QtWidgets.QApplication(sys.argv)
    win = wincore()
    win.show()
    sys.exit(app.exec_())
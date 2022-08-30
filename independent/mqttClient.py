
import threading
from loguru import logger
import time
import  json
import paho.mqtt.client as mqtt
from dotenv import find_dotenv, load_dotenv
import os
import mqttClient
import requests
import sys
import random
import faceApi
# 使用先创建.env配置文件
from requests_toolbelt.multipart.encoder import MultipartEncoder
class mqttClientFace(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.flag =False
        self.closeFlag = True
        self.taskStatus = ""
        self.netChangeCb = None
        self.inferCallbakc = None
        #当前连接状态
        self.connectStatus = False
        load_dotenv(find_dotenv('.env'))
        self.mqttServerName = os.environ.get("MQTT_SERVER_NAME")
        self.mqttServerPassword = os.environ.get("MQTT_SERVER_PASSWORD")
        self.mqttServerIp = os.environ.get("MQTT_SERVER_HOST")
        self.mqttServerPort = int(os.environ.get("MQTT_SERVER_PORT"))
        self.mqttId = os.environ.get("MQTT_ID")
        self.imgbed = os.environ.get("IMGBED")
        # print("-------------------")
        # print(self.mqttServerName)
        # print(self.mqttServerPassword)
        # print(self.mqttServerIp)
        # print(self.mqttServerPort)
        # print(self.mqttId)
        # print(self.imgbed)
        # print("-------------------")
        #图片的下周地址
        self.downloadImgPath = os.path.dirname(os.path.realpath(sys.argv[0])) + '\\faceData'
        self.init()

    def init(self):
        #face = mqttClient.mqttClientFace()
        self.client = mqtt.Client(client_id=self.mqttId,clean_session=False)
        
        self.client.on_connect = self.connectCb
        self.client.on_message = self.messageCb
        self.client.on_disconnect = self.disconnectCb
        self.client.on_publish = self.publishCb
        self.client.on_subscribe = self.subscribeCb
        # self.client.on_unsubscribe = self.on_unsubscribe

        #如果MQTT有账号密码
        if(self.mqttServerName != ""):
            self.client.username_pw_set(self.mqttServerName, self.mqttServerPassword)
        self.client.reconnect_delay_set(min_delay=1, max_delay=120)

        logger.info("网络通讯线程初始化结束")

        #初始化识别器
        self.api = faceApi.faceApi()

    def connect(self):
        try:
            self.client.connect(self.mqttServerIp, self.mqttServerPort, 60)  # 60为keepalive的时间间隔
        except:
            #会自动重连
            logger.warning("mqtt连接失败")

    def run(self):
        while 1:
            if(self.flag):
                self.connect()
                self.client.loop_forever()
            if(self.closeFlag == False):
                return True
            time.sleep(10)

    def go(self):
        if(self.flag == False):
            self.flag = True
            logger.info("网络通讯线程启动")

    def suspend(self):
        time.sleep(1)
        self.client.disconnect()
        self.flag = False
        logger.info("网络通讯线程暂停")

    def close(self):
        time.sleep(1)
        self.client.disconnect()
        self.flag = False
        self.closeFlag = False
        logger.info("网络通讯线程退出")

    def getStatus(self):
        temp = self.taskStatus
        self.taskStatus = ""
        return temp

    def getNetStatus(self):
        return self.connectStatus

   
    # 连接回调
    def connectCb(self,client, userdata, flags, rc):
        if(rc == 0):
            logger.info("MQTT连接建立")
            self.connectStatus = True
            if(self.netChangeCb):
                self.netChangeCb(self.connectStatus)
            self.client.subscribe([("faceRecognition/"+self.mqttId+"/addFace", 0), ("faceRecognition/"+self.mqttId+"/updateFaceLib", 0),("faceRecognition/"+self.mqttId+"/rct", 0)])
        else:
            # 1协议版本不正确  2客户端标识符无效 3服务器不可用 4用户名或密码错误 5未授权
            logger.info("MQTT连接被拒绝 {}".format(rc))
            
        #print("Connected with result code: " + str(rc))

    #连接断开回调 rc参数表示断开状态
    def disconnectCb(self,client, userdata, rc):
        logger.info("MQTT连接断开")
        self.connectStatus = False
        if(self.netChangeCb):
            self.netChangeCb(self.connectStatus)
        #print("Disconnected with result code "+str(rc))

    def messageCb(self,client, userdata, message):
        #print(message.topic)
        if(message.topic.find("addFace") != -1):
            logger.debug("任务：添加一张人脸图")
            try:
                resp = json.loads(message.payload.decode('utf-8'))
            except:
                logger.warning("格式错误")
                self.publishNormalAck(msgId,"json error")
                return False
            try:
                img = resp["img"]
                name = resp["name"]
                msgId = resp["msgId"]
            except:
                logger.warning("字段错误")
                self.publishNormalAck(msgId,"msg error")
                return False
            #首先下载图片，然后将图片加入的预备区    
            if(self.download(img,self.downloadImgPath,name+".jpg") == False):
                self.publishNormalAck(msgId,"download error")
            
            #然后将图片按照对应名称放
            self.api.input_new_face(name,self.downloadImgPath+"\\"+name+".jpg")
            self.publishNormalAck(msgId,"succeed")
        elif(message.topic.find("updateFaceLib") != -1):
            logger.info("任务：更新识别库")
            try:
                resp = json.loads(message.payload.decode('utf-8'))
            except:
                self.publishNormalAck(msgId,"json error")
                logger.warning("格式错误")
                return False
            try:
                msgId = resp["msgId"]
            except:
                logger.warning("字段错误")
                self.publishNormalAck(msgId,"msg error")
                return False
            self.api.data_align()
            self.api.update_facebank()
            self.publishNormalAck(msgId,"succeed")

        elif(message.topic.find("rct") != -1):
            logger.info("任务：识别")
            try:
                resp = json.loads(message.payload.decode('utf-8'))
            except:
                self.publishNormalAck(msgId,"json error")
                logger.warning("格式错误")
                return False
            try:
                img = resp["img"]
                msgId = resp["msgId"]
            except:
                self.publishNormalAck(msgId,"msg error")
                logger.warning("字段错误")
                return False      

            inferImgPath = os.path.dirname(os.path.realpath(sys.argv[0])) + '\\out'
            if(self.download(img,inferImgPath,msgId+".jpg") == False):
                self.publishNormalAck(msgId,"download error")
                return False
            inImgPath = inferImgPath + '\\' + msgId + ".jpg"
            outImgPath = inferImgPath + "\\" + msgId + "-infer.jpg"
            res = self.api.infer(inImgPath ,outImgPath )
            logger.debug("outImgPath:{}".format(outImgPath))
            if(res == None):
                self.publishNormalAck(msgId,"infer error")
            else:
                #上传图片
                file = open(outImgPath, 'rb')
                multipart_encoder = MultipartEncoder(
                    fields={"file":("test.jpg",file,"image/jpg")},
                )
                h={}
                h['Content-Type']=multipart_encoder.content_type
                postResult = requests.post(self.imgbed,data=multipart_encoder,headers=h)
                logger.info("img upload:{}".format(postResult.text))
                resImg = json.loads(postResult.text).get('data').get('url')
                self.publishRecognitionAck(msgId,resImg,res)
                # 结果回调
                if(self.inferCallbakc !=None):
                    nlist = ""
                    for n in res:
                        nlist = nlist + " " + n["name"]
                    self.inferCallbakc(msgId,outImgPath,nlist)

        else:
            logger.warning("warning","Received message '" + str(message.payload) + "' on topic '"
            + message.topic + "' with QoS " + str(message.qos))
            self.publishNormalAck(msgId,"topic error")
 
    #消息发送成功后的回调
    #对于Qos级别为1和2的消息，这意味着已经完成了与代理的握手。
    #对于Qos级别为0的消息，这只意味着消息离开了客户端。
    #mid变量与从相应的publish()返回的mid变量匹配
    def publishCb(self,client, userdata, mid):
        pass
        #print("mid: "+str(mid))

    # 识别结果应答 
    def publishRecognitionAck(self,msgId,url,res):
        #print(res)
        #print(type(res))
        nlist = []
        for n in res:
            nlist.append(n["name"])
        aItem={"msgId":msgId,"img":url,"result":nlist}
        ackJson = json.dumps(aItem, ensure_ascii=False)
        if(self.connectStatus == True):
            self.client.publish("faceRecognition/"+self.mqttId+"/recAck",ackJson)
            return True
        return False


    #通用应答
    def publishNormalAck(self,msgId,result):
        if(self.connectStatus == True):
            self.client.publish("faceRecognition/"+self.mqttId+"/ack", json.dumps({"msgId":msgId,"result":result}))
            return True
        return False

    def setCallback(self,netChange=None,inferCallback=None):
        self.netChangeCb = netChange
        self.inferCallbakc = inferCallback


    #订阅主题后的回调
    #mid变量匹配从相应的subscri be()返回的mid变量
    def subscribeCb(self,client, userdata, mid, granted_qos):
        logger.debug("Subscribed: {} , {}".format(str(mid),str(granted_qos)))
        


    def download(self, downloadURL,downloadPath, name):
        logger.debug("downloadURL={}".format(downloadURL))
        logger.debug("downloadPath={}".format(downloadPath+"\\"+name))
        """ 进行下载请求 """
        try:
            headers = {'content-type': "application/octet-stream",}
            re = requests.get(downloadURL,headers = headers,timeout=10)
            with open(downloadPath +"\\"+ name , "wb") as code:
                code.write(re.content)
                code.close()
                logger.info("下载完成{}".format(name))
                return True
        except:
            logger.warning("下载请求失败")
            return False
        
import keyboard


# def main():
#     face = mqttClientFace()
#     face.start()
#     face.go()
#     try:
#         while(1):
#             if keyboard.is_pressed('q'): 
#                 face.close()
#                 break
#             time.sleep(5)
#     except:
#         face.close()


# if __name__ == "__main__":
#         main()

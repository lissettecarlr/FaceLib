import os
import sys
import shutil
from config import *
from Retinaface import *
from recognizer.FaceRecognizer import *
import cv2
from recognizer.model import *
from loguru import logger

class faceApi():
    def __init__(self):
        self.init()

    def init(self):
        conf = get_config()
        self.facebank_path = conf.facebank_path
        self.detector = FaceDetector(name= "resnet",device=conf.device,weight_path = conf.work_path)
        self.face_rec = FaceRecognizer(conf)# name="ir_se50"

    # 将原始图像变为人脸图像 
    # input_path保存需要识别对象的文件夹，结构：
    # faceData
    #   - nameA
    #       - 1.jpg
    #       - 2.jpg
    #   - nameB
    #       - 1.jpg
    def data_align(self,input_path = None,save_path=None):
        logger.info("data align start")
        if(input_path == None):
            input_path = os.path.dirname(os.path.realpath(sys.argv[0]))  + "\\faceData"
            logger.debug("input_path使用默认路径{}".format(input_path))
        if(save_path == None):
            save_path = os.path.dirname(os.path.realpath(sys.argv[0])) + "\\data\\facebank"
            logger.debug("save_path使用默认路径{}".format(save_path))

        for root, dirs, files in os.walk(input_path, topdown=False):
            for name in dirs:
                dirs = os.listdir( os.path.join(root, name) )
                logger.info("start join people {}".format(name))
                for file in dirs:
                    img_path = os.path.join(root, name, file)
                    faceImg = cv2.imread(str(img_path))
                    face = self.detector.detect_align(faceImg)[0].cpu().numpy()

                    isExists = os.path.exists(save_path + "\\" + name)
                    if not isExists:
                        os.makedirs(save_path + "\\" + name)
                        logger.debug("创建文件夹{}".format(save_path + "\\" + name))
                    if len(face.shape) > 1:
                        savefile = save_path+"\\"+ name +"\\"+file
                        logger.info("{} img {} join success".format(name,file))
                        cv2.imwrite(savefile, face[0])
                    else:
                        logger.info("{} img {} join fail, not find face".format(name,file))
        
    # 加载识别对象的库
    def load_facebank(self):
        if os.path.exists(self.facebank_path) == False:
            logger.error("you don't have facebank yet: create with add_from_webcam or add_from_folder function")
            return None
        
        embs = torch.load(self.facebank_path + '/facebank.pth')
        names = np.load(self.facebank_path + '/names.npy')
        logger.info("load facebank success")
        return embs, names

    # 传入一张图片和姓名将其存入到预备区faceData
    # eg : python main.py -m input  -i D:\code\face\my\FaceLib\independent\faceData\test.jpg -n feng
    def input_new_face(self,name,faceImgPath):
        #先查找是否用同名文件夹，如果由则将图片放入，如果没有则创建新文件夹
        faceDataPath = os.path.dirname(os.path.realpath(sys.argv[0]))  + "\\faceData"
        if os.path.exists(faceDataPath + "\\" + name) == False:
            os.makedirs(faceDataPath + "\\" + name)
            logger.debug("创建文件夹{}".format(faceDataPath + "\\" + name))
            shutil.copyfile(faceImgPath,faceDataPath + "\\" + name + "\\" + "1.jpg")
            os.unlink(faceImgPath)
            logger.info("{} img {} input success .crt".format(name,faceImgPath))
        else:
            files = os.listdir(faceDataPath + "\\" + name)  
            imgNewName = str(len(files)+1) + ".jpg"
            shutil.move(faceImgPath,faceDataPath + "\\" + name + "\\" + imgNewName)
            logger.info("{} img {} input successm . move".format(name,faceImgPath))



    # 更新比对数据库，产出facebank.pth和names.npy
    def update_facebank(self,facebank_path=None,device=torch.device("cuda:0" if torch.cuda.is_available() else "cpu")):
        if(facebank_path == None):
            facebank_path = os.path.dirname(os.path.realpath(sys.argv[0]))  + "\\data\\facebank"
            logger.debug("识别库使用默认路径{}".format(facebank_path))

        if os.path.exists(facebank_path) == False:
            logger.error("not find facebank path")
            return None

        self.face_rec.model.eval()
        faces_embs = torch.empty(0).to(device)
        names = np.array(['Unknown'])

        logger.info("start update facebank")
        for root, dirs, files in os.walk(facebank_path, topdown=False):
            faceList = []
            # 循环所有检测对象的文件夹
            for name in dirs:
                logger.info("start join people {}".format(name))
                dirs = os.listdir( os.path.join(root, name) )
                
                #循环文件夹中的所有图
                for file in dirs:
                    img_path = os.path.join(root, name, file)
                    faceImg = cv2.imread(str(img_path))
                    if faceImg.shape[:2] != (112, 112):
                        logger.error("img {} not 112*112 , update is over".format(file))
                        return None
                    else:
                        faceImg = torch.tensor(faceImg).unsqueeze(0)
                    faceList.append(faceImg)

                faces = torch.cat(faceList)
                with torch.no_grad():
                    faces = faces_preprocessing(faces, device=device)
                    face_emb = self.face_rec.model(faces)
                    hflip_emb = self.face_rec.model(faces.flip(-1))  # image horizontal flip
                    face_embs = l2_norm(face_emb + hflip_emb)

                faces_embs = torch.cat((faces_embs, face_embs.mean(0, keepdim=True)))
                names = np.append(names, name)

        torch.save(faces_embs, facebank_path + '/facebank.pth')
        np.save(facebank_path +'/names', names)
        logger.info("update facebank success")
        return faces_embs, names

    #识别图片，识别返回None
    def infer(self,inputImgPath,outImgPath):
        targets, names = self.load_facebank()
        if(targets == None):
            return
        imgPath = inputImgPath
        # 判断该图片是否存在
        if(os.path.exists(imgPath) == False):
            logger.warning("not find img {}".format(imgPath))
            return None
        image = cv2.imread(imgPath)
        faces, boxes, scores, landmarks = self.detector.detect_align(image)
        if(len(faces.shape) > 1):
            results, score = self.face_rec.infer(faces, targets,tta=True)  # return min_idx, minimum
            #print(results,score)
        else:
            logger.warning("not find face")
            return None

        resList = []
        for idx, bbox in enumerate(boxes):
            special_draw(image, bbox, landmarks[idx], names[results[idx]+1], score[idx])
            res = {"name":names[results[idx]+1],"score":score[idx]}
            logger.info("name={},score={}".format(res["name"],res["score"]))
            resList.append(res)

        cv2.imwrite(outImgPath,image)
        return resList
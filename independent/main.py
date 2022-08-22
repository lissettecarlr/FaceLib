# 基于facelib改写的独立使用的人脸识别
# 流程：判断需要检测对象的数据集，对其后存入facebank中

import os
import sys
import shutil
# from config import *
# from Retinaface import *
from recognizer.FaceRecognizer import *
# from recognizer.model import *
from loguru import logger
from faceApi import *
import argparse

def main(args):
    face = faceApi()

    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('-m','--model', required=True ,choices=['find', 'input','update'])
    parser.add_argument('-i','--img', default='',help="input face image path")
    parser.add_argument('-o','--outImg', default='',help="output retinaface image path")
    parser.add_argument('-n','--imgName', default='',help="input face image name")
    args = parser.parse_args()

    if(args.model == "find"):
        face.infer(args.img,"./out/test.jpg")
    elif(args.model == "update"):
        face.data_align()
        face.update_facebank()
    elif(args.model == "input"):
        imgPath = args.img
        imgName = args.imgName
        face.input_new_face(imgName,imgPath)
    else:
        logger.warning("model error : {} ".format(args.model))
    return 


if __name__ == "__main__":
   main(sys.argv[1:])


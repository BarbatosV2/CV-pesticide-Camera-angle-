###########THIS CODE IS USED WITH YOLOV7###########
#REPLACE THE detect.py WITH THIS CODE#

#object detection

Change the detect.py to name.py 

#camera
python detect.py --weights weed.pt --conf 0.1 --img-size 640 --source 0

#video
python detect.py --weights weed.pt --conf 0.25 --img-size 640 --source weed.mp4

#images
python detect.py --weights weed.pt --conf 0.25 --img-size 640 --source inference/images/42.jpg

#model training for object detection

#batch size and workers will depends... larger batch size sometimes make gpu memory insufficient

python train.py --workers 1 --device 0 --batch-size 2 --data data/custom.yaml --img 640 640 --cfg cfg/training/yolov7custom.yaml --weights '' --name customyolov7 --hyp data/hyp.scratch.p5.yaml

python train.py --workers 8 --device 0 --batch-size 2 --data data/laser_weed.yaml --img 640 640 --cfg cfg/training/laser_weed.yaml --weights '' --name laserweedv5 --hyp data/hyp.scratch.p5.yaml    #better to train with this for accuracy

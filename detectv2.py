import argparse
import time
from pathlib import Path
import math
import cv2
import torch
import torch.backends.cudnn as cudnn
import numpy as np
from numpy import random

from models.experimental import attempt_load
from utils.datasets import LoadStreams, LoadImages
from utils.generals import check_img_size, check_requirements, check_imshow, non_max_suppression, apply_classifier, \
    scale_coords, xyxy2xywh, strip_optimizer, set_logging, increment_path
from utils.plots import plot_one_box
from utils.torch_utilss import select_device, load_classifier, time_synchronized, TracedModel

def detect(save_img=False):
    source, weights, view_img, save_txt, imgsz, trace = opt.source, opt.weights, opt.view_img, opt.save_txt, opt.img_size, not opt.no_trace
    save_img = not opt.nosave and not source.endswith('.txt')  # save inference images
    webcam = source.isnumeric() or source.endswith('.txt') or source.lower().startswith(
        ('rtsp://', 'rtmp://', 'http://', 'https://'))

    # Directories
    save_dir = Path(increment_path(Path(opt.project) / opt.name, exist_ok=opt.exist_ok))  # increment run
    (save_dir / 'labels' if save_txt else save_dir).mkdir(parents=True, exist_ok=True)  # make dir

    # Initialize
    set_logging()
    device = select_device(opt.device)
    half = device.type != 'cpu'  # half precision only supported on CUDA

    # Load model
    model = attempt_load(weights, map_location=device)  # load FP32 model
    stride = int(model.stride.max())  # model stride
    imgsz = check_img_size(imgsz, s=stride)  # check img_size

    if trace:
        model = TracedModel(model, device, opt.img_size)

    if half:
        model.half()  # to FP16

    # Second-stage classifier
    classify = False
    if classify:
        modelc = load_classifier(name='resnet101', n=2)  # initialize
        modelc.load_state_dict(torch.load('weights/resnet101.pt', map_location=device)['model']).to(device).eval()

    # Set Dataloader
    vid_path, vid_writer = None, None
    if webcam:
        view_img = check_imshow()
        cudnn.benchmark = True  # set True to speed up constant image size inference
        dataset = LoadStreams(source, img_size=imgsz, stride=stride)
        
    else:
        dataset = LoadImages(source, img_size=imgsz, stride=stride)

    # Get names and colors
    names = model.module.names if hasattr(model, 'module') else model.names
    colors = [[random.randint(0, 255) for _ in range(3)] for _ in names]

    # Run inference
    if device.type != 'cpu':
        model(torch.zeros(1, 3, imgsz, imgsz).to(device).type_as(next(model.parameters())))  # run once
    old_img_w = old_img_h = imgsz
    old_img_b = 1

    t0 = time.time()
    for path, img, im0s, vid_cap in dataset:
        img = torch.from_numpy(img).to(device)
        img = img.half() if half else img.float()  # uint8 to fp16/32
        img /= 255.0  # 0 - 255 to 0.0 - 1.0
        if img.ndimension() == 3:
            img = img.unsqueeze(0)

        # Warmup
        if device.type != 'cpu' and (old_img_b != img.shape[0] or old_img_h != img.shape[2] or old_img_w != img.shape[3]):
            old_img_b = img.shape[0]
            old_img_h = img.shape[2]
            old_img_w = img.shape[3]
            for i in range(3):
                model(img, augment=opt.augment)[0]

        # Inference
        t1 = time_synchronized()
        with torch.no_grad():   # Calculating gradients would cause a GPU memory leak
            pred = model(img, augment=opt.augment)[0]
        t2 = time_synchronized()

        # Apply NMS
        pred = non_max_suppression(pred, opt.conf_thres, opt.iou_thres, classes=opt.classes, agnostic=opt.agnostic_nms)
        t3 = time_synchronized()

        # Apply Classifier
        if classify:
            pred = apply_classifier(pred, modelc, img, im0s)

        # Process detections
        for i, det in enumerate(pred):  # detections per image
            if webcam:  # batch_size >= 1
                p, s, im0, frame = path[i], '%g: ' % i, im0s[i].copy(), dataset.count
           
            else:
                p, s, im0, frame = path, '', im0s, getattr(dataset, 'frame', 0)
                #cv2.line(frame, (639, 500), (60,50), (0,255,0), 2)
                
            p = Path(p)  # to Path
            save_path = str(save_dir / p.name)  # img.jpg
            txt_path = str(save_dir / 'labels' / p.stem) + ('' if dataset.mode == 'image' else f'_{frame}')  # img.txt
            gn = torch.tensor(im0.shape)[[1, 0, 1, 0]]  # normalization gain whwh
            
            xyxy = [0,0,0,0]
            if len(det):
                # Rescale boxes from img_size to im0 size
                det[:, :4] = scale_coords(img.shape[2:], det[:, :4], im0.shape).round()
                
                # Print results
                for c in det[:, -1].unique():
                    n = (det[:, -1] == c).sum()  # detections per class
                    s += f"{n} {names[int(c)]}{'s' * (n > 1)}, "  # add to string

                # Write results                                                                                          
                for *xyxy, conf, cls in reversed(det):
                    
                    if save_txt:  # Write to file
                        xywh = (xyxy2xywh(torch.tensor(xyxy).view(1, 4)) / gn).view(-1).tolist()  # normalized xywh
                        line = (cls, *xywh, conf) if opt.save_conf else (cls, *xywh)  # label format
                        with open(txt_path + '.txt', 'a') as f:
                            f.write(('%g ' * len(line)).rstrip() % line + '\n')

                    if save_img or view_img:  # Add bbox to image
                        label = f'{names[int(cls)]} {conf:.2f}'
                        plot_one_box(xyxy, im0, label=label, color=colors[int(cls)], line_thickness=1)
                    
                
            #infos
            #all the distance are pixels value
            #https://www.kowa-lenses.com/en/lens-calculator for calculation of camera specs 
            #working distance = 890mm
            #focal length = 2.8mm
            #horizontal view = 1506.3       #2.354mm per pixels by dividing view with pixel specs
            #vertical view = 1116.8         (took nearest value)
            #horizontal angle = 108°    #38.66   #77.32
            #vertical angle = 54°       #28.072     #56.144
            
            ox = (xyxy[0]+xyxy[2])/2    #x location of bonded object
            oy = (xyxy[1]+xyxy[3])/2     #y location of bonded object
            # Print time (inference + NMS)
            print(f'{s}Done. ({(1E3 * (t2 - t1)):.1f}ms) Inference, ({(1E3 * (t3 - t2)):.1f}ms) NMS')
            
            #print("x =", (xyxy[0]+xyxy[2])/2, " y =", (xyxy[1]+xyxy[3])/2)  #coordinate of bounded object 
            
            print("object bounded location =",ox, oy)
            #size of the source 
            
            w = im0.shape[1]/2
            h = im0.shape[0]/2
            print("centre of the source =",w,h) #centre of the source
            
            cv2.line(im0, (320, 0), (320,480), (0,255,0), 1)
            cv2.line(im0, (160, 0), (160,480), (0,255,0), 1)
            cv2.line(im0, (480, 0), (480,480), (0,255,0), 1)
            cv2.line(im0, (0, 240), (640,240), (0,255,0), 1)
            cv2.line(im0, (0, 120), (640,120), (0,255,0), 1)
            cv2.line(im0, (0, 180), (640,180), (0,255,0), 1)
            cv2.line(im0, (0, 360), (640,360), (0,255,0), 1)
            
            
            #capture = cv2.VideoCapture
            #width, height, channels = capture.shape[:2]h
            #print(width, height)
            
            #calculation of distance between weed coordinate and centre
            #camera point pixel view
            
            if not ox or oy:
                    
                #c = math.sqrt((a**2)+(b**2)) #the distance between weed and centre of source
                #print("distance between the source's centre and the object =",c)
                
                ################### testing site ####################### need recheck if correct or not
                #all the distance value are pixels 
                
                #assuming that the camera is in right angle (actual angle 110)
                #for ariel view (as the camera is not in the centre)
                #to find out the distance between camera and the object's y location
                height = 740 #930   #we know already (centimetre but assuming as pixel value)
                #to find width 
                ydegree =  27.9#18.5 #27.95
                pixely = (ydegree*2)/480         #28.072       #28. is good

                smalltria = (height/math.sin(math.radians(72.9)))*math.sin(math.radians(90)) #73.072               #change to radian (not)
                print("A =",smalltria)
                
                hipo = (smalltria/math.sin(math.radians(45)))*math.sin(math.radians(107.1))  #106.928
                print("hipo =", hipo)
                
                #base45 = (smalltria/math.sin(math.radians(45)))*math.sin(math.radians(37.5))
                #print("base a =", base45)
                
                #baseb = (hipo/math.sin(math.radians(7.5)))*math.sin(math.radians(37.5))
                #print("base b =", baseb)
                
                #print("whole base =", basea + baseb)
                #730 divided by sin(45) 
                
                #x = (730/math.sin(math.radians(82.5)))*math.sin(math.radians(7.5))
                #print("x =", x)
                bigangle = 180 - (ydegree + 45)
                
                smallangle = bigangle - 90
                nonCamBase = (smalltria/math.sin(math.radians(90)))*math.sin(math.radians(smallangle))
                print("non-Camera-base =", nonCamBase)

                y = 480-oy
                baseX = (smalltria/math.sin(math.radians(73.072-(y*pixely))))*math.sin(math.radians(y*pixely))
                print("baseX =",baseX + nonCamBase)

                #for horizontal 

                hipoX = (smalltria/math.sin(math.radians(73.072-(y*pixely))))*math.sin(math.radians(106.928))
                print("hipoX =", hipoX)


                pixelx = (34.12*2)/640       #42  #38.66
                
                if ox < 320:
                    z=320-ox
                    baseY = hipoX/math.sin(math.radians(90-(z*pixelx)))*(math.sin(math.radians(z*pixelx)))
                    print("baseY =", baseY)
                if ox >= 320:
                    z= ox-320
                    baseY = hipoX/math.sin(math.radians(90-(z*pixelx)))*(math.sin(math.radians(z*pixelx)))
                    print("baseY =", baseY)
                
                camobjdis = math.sqrt((baseX**2)+(baseY**2))
                print("distance between camera and object =", camobjdis)
                
                #grounddisy = x + (cameraobjecty*2.354)
                #print("distance between middle end frame =", grounddisy)
                
                #grounddistance = math.sqrt((grounddisy**2)+(a**2))
                
                #print("the distance between middle ground frame and object distance =", grounddistance)
                
                ####################### POV THE CAMERA ANGLE ###########################
                
                #cameraobjectyangle = cameraobjecty * 0.1875         #ratio degree per pixel
                #cameraobjang = cameraobjecty * 0.3125               #0.3125    #0.15625 
                
                #objecty = ((smalltria/math.sin(math.radians(cameraobjectyangle)))*math.sin(math.radians(cameraobjang)))*2.354
                
                #print("distance between object's y and camera =",objecty) 
                
                #to find out the distance between camera and object's x location
                #will know where the object is left or right as we know the object location
                
                #camobjectdistance =  math.sqrt(((a*2.354)**2)+((objecty)**2))
                
                #objectx = (objecty/math.sin(math.radians(90))) * math.sin(math.radians(41))
                #print("the distance between the camera and the object =", objectx)
                
                ################################################################################
                
                #to know where the object is (left or right)
                if ox > w:
                    print("the object is on the right")
                else:
                    print("the object is on the left")
                
            if xyxy == [0,0,0,0]: 
                print("No object detected") 

            # Stream results
            if view_img:
                
                #camera matrix
                mtx = np.array([[482.82559214,   0,         316.84971798],
                                [  0.  ,       474.26771942, 220.14107613],
                                [  0.   ,        0.      ,     1.        ]])

                #distortion coefficients
                dist = np.array([-4.07062414e-01, 1.73160312e-01, 1.49009489e-02, 5.07985436e-06, -2.75905543e-02])
                
                #camera calibration method
                im0 = cv2.undistort(im0, mtx, dist)

                cv2.imshow(str(p), im0)             #camera output
                
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break  # 1 millisecond       

            # Save results (image with detections)
            if save_img:
                if dataset.mode == 'image':
                    cv2.imwrite(save_path, im0)
                    print(f" The image with the result is saved in: {save_path}")
                else:  # 'video' or 'stream'
                    if vid_path != save_path:  # new video
                        vid_path = save_path
                        if isinstance(vid_writer, cv2.VideoWriter):
                            vid_writer.release()  # release previous video writer
                        if vid_cap:  # video
                            fps = vid_cap.get(cv2.CAP_PROP_FPS)
                            w = int(vid_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                            h = int(vid_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                                
                            print(w,h)
                        else:  # stream
                            fps, w, h = 30, im0.shape[1], im0.shape[0]
                            save_path += '.mp4'
                        vid_writer = cv2.VideoWriter(save_path, cv2.VideoWriter_fourcc(*'mp4v'), fps, (w, h))
                    vid_writer.write(im0)
                    
        if cv2.waitKey(1) & 0xFF == ('q'):
            break

    if save_txt or save_img:
        s = f"\n{len(list(save_dir.glob('labels/*.txt')))} labels saved to {save_dir / 'labels'}" if save_txt else ''
        #print(f"Results saved to {save_dir}{s}")

    print(f'Done. ({time.time() - t0:.3f}s)')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--weights', nargs='+', type=str, default='yolov7.pt', help='model.pt path(s)')
    parser.add_argument('--source', type=str, default='inference/images', help='source')  # file/folder, 0 for webcam
    parser.add_argument('--img-size', type=int, default=640, help='inference size (pixels)')
    parser.add_argument('--conf-thres', type=float, default=0.25, help='object confidence threshold')
    parser.add_argument('--iou-thres', type=float, default=0.45, help='IOU threshold for NMS')
    parser.add_argument('--device', default='', help='cuda device, i.e. 0 or 0,1,2,3 or cpu')
    parser.add_argument('--view-img', action='store_true', help='display results')
    parser.add_argument('--save-txt', action='store_true', help='save results to *.txt')
    parser.add_argument('--save-conf', action='store_true', help='save confidences in --save-txt labels')
    parser.add_argument('--nosave', action='store_true', help='do not save images/videos')
    parser.add_argument('--classes', nargs='+', type=int, help='filter by class: --class 0, or --class 0 2 3')
    parser.add_argument('--agnostic-nms', action='store_true', help='class-agnostic NMS')
    parser.add_argument('--augment', action='store_true', help='augmented inference')
    parser.add_argument('--update', action='store_true', help='update all models')
    parser.add_argument('--project', default='runs/detect', help='save results to project/name')
    parser.add_argument('--name', default='exp', help='save results to project/name')
    parser.add_argument('--exist-ok', action='store_true', help='existing project/name ok, do not increment')
    parser.add_argument('--no-trace', action='store_true', help='don`t trace model')
    opt = parser.parse_args()
    print(opt)
    #check_requirements(exclude=('pycocotools', 'thop'))

    with torch.no_grad():
        if opt.update:  # update all models (to fix SourceChangeWarning)
            for opt.weights in ['yolov7.pt']:
                detect()
                strip_optimizer(opt.weights)
        else:
            detect()
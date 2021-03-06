# -*- coding: utf-8 -*-


#模板匹配
from re import split
import cv2
import numpy as np
import numpy 
import win32gui 
import win32api
import win32ui
import win32con
import win32con as wcon
import pynput
import time
import ctypes
from ctypes import *
from PIL import ImageGrab,Image

from utils import * 
import re 
import random
import string
#jit是进行numpy运算
from numba import jit

aperture = (180,180,150)

#大雁塔入口 在坐标442，242位置
pls = (( 1059,  268, 0x4e3011),(1059,  269, 0x4f310e),)

#jit模式下调试有限



numbers_images = {'0':"num_0",'1':"num_1",'2':"num_2",'3':"num_3",'4':"num_4",'5':"num_5",'6':"num_6",
           '7':"num_7",'8':"num_8",'9':"num_9"}

def binstr_to_nparray(hex_2_str,abs_x,abs_y):
    binary = np.zeros((abs_y,abs_x), dtype=np.uint8)
    i = 0
    for j in range(abs_x):
        for k in range(abs_y):
            if hex_2_str[i] == "0":
                binary[k][j]=0
            else:
                binary[k][j]=255
            i+=1
    return binary

def get_window_rect(hwnd):
    try:
        f = ctypes.windll.dwmapi.DwmGetWindowAttribute
    except WindowsError:
        f = None
    if f:
        rect = ctypes.wintypes.RECT()
        DWMWA_EXTENDED_FRAME_BOUNDS = 9
        f(ctypes.wintypes.HWND(hwnd),
          ctypes.wintypes.DWORD(DWMWA_EXTENDED_FRAME_BOUNDS),
          ctypes.byref(rect),
          ctypes.sizeof(rect)
          )
        return rect.left, rect.top, rect.right, rect.bottom

class Robot:
    def __init__(self,class_name,title_name,zoom_count):
        self.class_name = class_name
        self.title_name = title_name
        #窗口坐标
        self.left = 0
        self.top = 0 
        self.right = 0
        self.bottom = 0
        self.hwnd = None
        self.ScreenBoardhwnd = None
        self.game_width = 0
        self.game_height = 0
        self.zoom_count = zoom_count
        self.rollback_list = list() #回滚机制，在于颜色匹配没找到或者卡屏的情况,根据此列表操作步骤重新回滚。
        
    @staticmethod
    @jit
    def __findMultiColor(s_c,expectedRGBColor,tolerance,width = 1919,height = 1079):
        pos_x_y = []
        for y in range(height):
            for x in range(width):
                b,g,r = s_c[y,x]
                exR, exG, exB = expectedRGBColor[:3]
                if (abs(r - exR) <= tolerance) and (abs(g - exG) <= tolerance) and (abs(b - exB) <= tolerance):
                    pos_x_y.append((x,y))
        return pos_x_y
    



    #像素转换成二值化点阵，返回二进制字符串
    @staticmethod
    @jit
    def rgb_to_hexstr_2(image_arrays,binary,scx_rgb,__mean_s_r,__mean_s_g,__mean_s_b,__mean_e_r,__mean_e_g,__mean_e_b,x1,y1,x2,y2):
        for idx ,x in enumerate (range(x1,x2)):
            for idy, y in enumerate (range(y1,y2)):
                b,g,r = image_arrays[y,x]
                if  (r<__mean_s_r*2) and (g<(__mean_s_g*2)) and (b<(__mean_s_b*2)):
                    binary[idy,idx] = 255
                else:
                    binary[idy,idx] = 0
        return binary
        
    
    def Get_GameHwnd(self):
        self.hwnd= win32gui.FindWindow('Qt5QWindowIcon','夜神模拟器')
        self.ScreenBoardhwnd = win32gui.FindWindowEx(self.hwnd, 0, 'Qt5QWindowIcon', 'ScreenBoardClassWindow')
        self.hwnd = win32gui.FindWindowEx(self.ScreenBoardhwnd, 0, self.class_name, self.title_name)
        print('hwnd=',self.hwnd)
        text = win32gui.GetWindowText(self.hwnd)
        if self.hwnd:
            print("found game hwnd")
            self.left,self.top,self.right,self.bottom = win32gui.GetWindowRect(self.hwnd)
            #窗口坐标
            self.left=int(self.left*self.zoom_count)
            self.top=int(self.top*self.zoom_count )
            self.right=int(self.right*self.zoom_count )
            self.bottom=int(self.bottom*self.zoom_count ) 
            
            print("The window coordinates: ({0},{1},{2},{3})".format(str(self.left),str(self.top),str(self.right),str(self.bottom)))
            self.game_width = self.right - self.left
            self.game_height = self.bottom - self.top
            
        else:
            print("Not found game hwnd")
    """
    x,y = findMultiColorInRegionFuzzy( 0xef6fdc, "24|5|0xffeecb,-7|30|0x2fb7ff", 90, 0, 0, 1919, 1079)
    """
    def findMultiColorInRegionFuzzy(self,color,posandcolor,degree,x1=None,y1=None,x2=None,y2=None,tab=None):
        x = None
        y = None
        tolerance = 100 - degree
        r,g,b  = Hex_to_RGB(color)
        tpl = self.Print_screen()
        posandcolor_list = list()
        posandcolors_param = posandcolor.split(",")
        state = State.OK
        pos_x_y_list = self.__findMultiColor(tpl,(r,g,b),tolerance)   
        if pos_x_y_list:
            for p in posandcolors_param:
                __c = p.split("|")
                px = __c[0]
                py = __c[1]
                rgb_hex = __c[2]
                _tmp = {"px":int(px),"py":int(py),"rgb_hex":rgb_hex}
                posandcolor_list.append(_tmp)
            for x,y in pos_x_y_list:
                for p in posandcolor_list:
                    __px = p["px"]
                    __py = p["py"]
                    __rgb_hex = p["rgb_hex"]
                    b,g,r = tpl[y+__py,x+__px]
                    exR = int(__rgb_hex[2:4],16) 
                    exG = int(__rgb_hex[4:6],16) 
                    exB = int(__rgb_hex[6:8],16) 
                    if (pixelMatchesColor((r, g, b),(exR,exG,exB),tolerance)):
                        state = State.OK
                    else:
                        state = State.NOTMATCH
                        break
                if state == State.OK:
                    return x,y
        return (-1,-1)
        
        
        
            
    def Print_screen(self):
        
        #返回句柄窗口的设备环境，覆盖整个窗口，包括非客户区，标题栏，菜单，边框
        hWndDC = win32gui.GetWindowDC(self.hwnd)
        #创建设备描述表
        mfcDC = win32ui.CreateDCFromHandle(hWndDC)
        #创建内存设备描述表
        saveDC = mfcDC.CreateCompatibleDC()
        #创建位图对象准备保存图片
        saveBitMap = win32ui.CreateBitmap()
        #为bitmap开辟存储空间
        saveBitMap.CreateCompatibleBitmap(mfcDC,self.game_width,self.game_height)
        #将截图保存到saveBitMap中
        saveDC.SelectObject(saveBitMap)
        #保存bitmap到内存设备描述表
        saveDC.BitBlt((0,0), (self.game_width,self.game_height), mfcDC, (0, 0), win32con.SRCCOPY)
 
        signedIntsArray = saveBitMap.GetBitmapBits(True)
        
        win32gui.DeleteObject(saveBitMap.GetHandle())
        saveDC.DeleteDC()
        mfcDC.DeleteDC()
        win32gui.ReleaseDC(self.hwnd, hWndDC)
        
        salt = ''.join(random.sample(string.ascii_letters + string.digits, 8))
        
        im_PIL = Image.frombuffer(
            'RGB',
            (self.game_width, self.game_height),
            signedIntsArray, 'raw', 'BGRX', 0, 1)
        # im_PIL.save("C:\\Users\\Wrench\\Desktop\\tmp\\im_opencv_" + salt + ".png")
        # im = Image.open("C:\\Users\\Wrench\\Desktop\\tmp\\im_opencv_" + salt + ".png")
        return cv2.cvtColor(np.array(im_PIL),cv2.COLOR_RGB2BGR)
    
    def doClick(self,cx,cy):
        ctr = pynput.mouse.Controller()
        ctr.move(cx, cy)   #鼠标移动到(x,y)位置
        ctr.press(pynput.mouse.Button.left)  #移动并且在(x,y)位置左击
        ctr.release(pynput.mouse.Button.left) 
    def getCurPos(self):
        return win32gui.GetCursorPos()
    
    def getPos(self):
        while True:
            res = getCurPos()
            print (res)
            time.sleep(1)
            
    def clickLeft(self):
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN | win32con.MOUSEEVENTF_LEFTUP, 0, 0)

    def movePos(self,x, y):
        windll.user32.SetCursorPos(x, y)

    def animateMove(self,curPos, targetPos, durTime=1, fps=60):
        x1 = curPos[0]
        y1 = curPos[1]
        x2 = targetPos[0]
        y2 = targetPos[1]
        dx = x2 - x1
        dy = y2 - y1
        times = int(fps * durTime)
        dx_ = dx * 1.0 / times
        dy_ = dy * 1.0 / times
        sleep_time = durTime * 1.0 / times
        for i in range(times):
            int_temp_x = int(round(x1 + (i + 1) * dx_))
            int_temp_y = int(round(y1 + (i + 1) * dy_))
            windll.user32.SetCursorPos(int_temp_x, int_temp_y)
            time.sleep(sleep_time)
        windll.user32.SetCursorPos(x2, y2)
        
    


    def animateMoveAndClick(self,curPos, targetPos, durTime=0.5, fps=30, waitTime=0.5):
        x1 = curPos[0]
        y1 = curPos[1]
        x2 = targetPos[0]
        y2 = targetPos[1]
        dx = x2 - x1
        dy = y2 - y1
        times = int(fps * durTime)
        dx_ = dx * 1.0 / times
        dy_ = dy * 1.0 / times
        sleep_time = durTime * 1.0 / times

        for i in range(times):
            int_temp_x = int(round(x1 + (i + 1) * dx_))
            int_temp_y = int(round(y1 + (i + 1) * dy_))
            windll.user32.SetCursorPos(int_temp_x, int_temp_y)
            time.sleep(sleep_time)
        windll.user32.SetCursorPos(x2, y2)
        time.sleep(waitTime)
        self.clickLeft()

    def matchTemplate(self,tpl,target,tolerance=0.2):
        methods = [cv2.TM_SQDIFF_NORMED]   #3种模板匹配方法 cv2.TM_CCORR_NORMED, cv2.TM_CCOEFF_NORMED
        th, tw = target.shape[:2]
        
        for md in methods:
            #result = cv2.matchTemplate(tpl,target, md)
            try:
                result =cv2.matchTemplate(tpl,target, md)
                ok = True
            except cv2.error as e: 
                ok = False
                print("匹配错误")
                return (-1,-1)
            
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            if min_val > tolerance:
                print("not match")
                return (-1,-1)
            else:
                pass
                
            if md == cv2.TM_SQDIFF_NORMED:
                tl = min_loc
            else:
                tl = max_loc
            br = (tl[0]+tw, tl[1]+th)   #br是矩形右下角的点的坐标
            a=int((tl[0]+int(tw/2)))
            b=int((tl[1]+int(th/2)))
            #new_target = (a,b)
            # cv2.rectangle(tpl,tl,br,(0, 0, 255),1)  
            # cv2.imshow('t',tpl)  
            # cv2.waitKey(0)  
            return a,b     
        
    def clike_map(self):
        tpl = self.Print_screen() 
        target = cv2.imread("./images/map.jpg")  
        new_target = self.matchTemplate(tpl,target)    
        self.click(new_target) 
        
    
    def clike_x_map(self,number:str):
        global numbers_images
        tpl = self.Print_screen() 
        target = cv2.imread("./images/map_x.jpg") 
        x,y = self.matchTemplate(tpl,target)
        self.click(x,y)
        time.sleep(1)
        
        number_list = [n for n in number]
        for n in number_list:
            tpl = self.Print_screen() 
            number_images = "./images/"+ numbers_images[n] + ".jpg"
            X_t = cv2.imread(number_images) 
            x,y = self.matchTemplate(tpl,X_t)
            self.click(x,y)
            
            
        tpl = self.Print_screen() 
        target = cv2.imread("./images/ok.jpg")
        x,y = self.matchTemplate(tpl,target)
        self.click(x,y)
        time.sleep(1) 
        
            
    def clike_y_map(self,number:str):
        global numbers_images
        tpl = self.Print_screen() 
        target = cv2.imread("./images/map_y.jpg") 
        x,y = self.matchTemplate(tpl,target)
        self.click(x,y)
        time.sleep(1)
        number_list = [n for n in number]
        for n in number_list:
            tpl = self.Print_screen() 
            number_images = "./images/"+ numbers_images[n] + ".jpg"
            X_t = cv2.imread(number_images) 
            new_X_t = self.matchTemplate(tpl,X_t)
            self.animateMoveAndClick(self.getCurPos(),new_X_t)
        tpl = self.Print_screen() 
        target = cv2.imread("./images/ok.jpg")
        x,y = self.matchTemplate(tpl,target)
        self.click(x,y)
        time.sleep(1)    
        
    def clike_expr_tool(self):
        tpl = self.Print_screen() 
        target = cv2.imread("./images/expr_tool.jpg")
        x,y = self.matchTemplate(tpl,target)
        self.click(x,y)
        
    def clike_aperture(self):
        # LUA 脚本插件 {1338,949,0x121721} 1338,949 是 x,y这样.  0x121721 是rbg的十六进制码
        im2 = ImageGrab.grab(bbox =(0, 0, 300, 300)) 
        pix = im2.load()
        sc = pix[55,56]
        tpl = self.Print_screen()
        #x,y是这个3维图像的位置. 第一参数是y,第二个是x
        r, g, b = tpl[1079,1919]
        a = (r, g, b)
        print (a)
        
    def look_up_color_by_xy_c(self,x:int,y:int,rgb_hex):
        ret = None
        tpl = self.Print_screen()
        
        rgb_tuple = Hex_to_RGB(str(rgb_hex))

        b,g,r = tpl[y,x]
        hex_str = '%02x%02x%02x' % (r, g, b)
        print(hex_str)
        hex_a = int(hex_str,16)
        if pixelMatchesColor((r, g, b),(78,48,17),10):
            print ("Matches Color")
            ret = State.OK
        else:
            print ("Not Found! Rollback it")
            ret = State.ROLLBACK
        return ret
    
    def check_fire(self):
        tpl = self.Print_screen()
        target = cv2.imread("./images/check_fire.jpg")
        x,y = self.matchTemplate(tpl,target)
        if x == -1:
            return False
        else:
            return True
        
    
    def click(self,x:int=None,y:int=None):
            """Click at pixel xy."""
            x = int(x/1.5)#1.5是缩放比例
            y = int(y/1.5)
            lParam = win32api.MAKELONG(x, y)
            win32gui.PostMessage(self.ScreenBoardhwnd, wcon.WM_MOUSEMOVE,wcon.MK_LBUTTON, lParam)
            win32gui.SendMessage(self.ScreenBoardhwnd,  wcon.WM_SETCURSOR, self.ScreenBoardhwnd, win32api.MAKELONG(wcon.HTCLIENT, wcon.WM_LBUTTONDOWN))
            # win32gui.PostMessage(self.ScreenBoardhwnd, wcon.WM_SETCURSOR, 0, 0)
            while (win32api.GetKeyState(wcon.VK_CONTROL) < 0 or
                 win32api.GetKeyState(wcon.VK_SHIFT) < 0 or
                 win32api.GetKeyState(wcon.VK_MENU) < 0):
                 time.sleep(0.005)
            win32gui.PostMessage(self.ScreenBoardhwnd, wcon.WM_LBUTTONDOWN,
                                 wcon.MK_LBUTTON, lParam)
            win32gui.PostMessage(self.ScreenBoardhwnd, wcon.WM_LBUTTONUP, 0, lParam)
            
    def fire(self):
        #check autofire
        tpl = self.Print_screen()
        target = cv2.imread("./images/auto.jpg")
        x,y = self.matchTemplate(tpl,target)
        if x == -1:
            print("正在自动战斗中")
        else:
            print("点击自动战斗 posx:{0} posy:{1}".format(x,y))
            self.click(x,y)
            


                    
    def __Ocrtext(self,tab,scx_rgb,x1,y1,x2,y2):
        tpl = self.Print_screen()
        se_rgb_tupe = scx_rgb.split(",")
        
        __mean_s_r = int(se_rgb_tupe[0][0:2],16)
        __mean_s_g = int(se_rgb_tupe[0][2:4],16)
        __mean_s_b = int(se_rgb_tupe[0][4:6],16)
        
        
        __mean_e_r = int(se_rgb_tupe[1][0:2],16)
        __mean_e_g = int(se_rgb_tupe[1][2:4],16)
        __mean_e_b = int(se_rgb_tupe[1][4:6],16)
        
        binary = np.zeros((abs(y2-y1),abs(x2-x1)), dtype=np.uint8)
        
        bin_2_ = self.rgb_to_hexstr_2(tpl,binary,scx_rgb,__mean_s_r,__mean_s_g,__mean_s_b,__mean_e_r,__mean_e_g,__mean_e_b,x1,y1,x2,y2)
                
        return bin_2_
    
    def Ocrtext(self,tab,scx_rgb,x1,y1,x2,y2):
        
        #ret = re.findall(r"@(.*?)\$",tab,re.I|re.M)
        data_tuple = tab.split("@")[1]
        data_tuple = data_tuple.split("$")
        if len(data_tuple):
            p_hexstr_2 = data_tuple[0]
            hex_str_16 = tab.split("@")[0]
            hexstr_2 = hexstr_16_to_hexstr_2(hex_str_16)
            hexstr_2 += p_hexstr_2
            word = data_tuple[1]
            x =  int(data_tuple[4])
            y = int(data_tuple[3])
            image_array = binstr_to_nparray(hexstr_2,x,y)
            image_array1 = self.__Ocrtext(hexstr_2,scx_rgb,x1, y1, x2, y2)
            new_X_t = self.matchTemplate(image_array1,image_array,0.1)
            print(new_X_t)
            if new_X_t !=(-1,-1):
                print("当前识字为:{0}".format(word))
                return word

def robot_fire(blRobot):
    #tql = blRobot.Print_screen()
    while True:
        bfire = blRobot.check_fire()
    print("check_fire:{0}".format(bfire))
    if bfire:
        blRobot.fire()    
                 
        
def main():
    blRobot = Robot(class_name="subWin",title_name="sub",zoom_count=1.5)
    blRobot.Get_GameHwnd()
    start = time.time()
    xstr = blRobot.Ocrtext("0003c0000000f00000003c0000000f00000003c0000000f80007fffffff9ffffffff7fffffffcffffffff0003c0078000f003e003fc00f000ff003c003fc00e001ef801000f3fc00003cff80001e3ff000078fbe0003c3c7c001f0f0f800f83c0f003c0f03e01f03c03c0f80f00f83c03c01f0e00f003c1003c00f0000f001e0003c00380006000400000000000000000000000000000000000ff30003c3fce000f0ff38003c3e0e000f0e038f03c300ffc0f0c03ff838300ffe0e0c03fbc78301fcf1c0c3fc1cf079ff03bc3eff80ff1fbfe03fcfc0380fe1f00e03f83c03807c0f00e01f01c0380fc0300e07f00c0387fc0300f3ff00c03ff1e0300ffc3c0c03f80f0300f803c0c03800f0380e001e0ff38007c3fce000f0ff38003c1f8400070000000000000000000100010000c000c000300070001f003c03ffffff01ffffffc07fffffe00ffffff00007803c7c00c00fbf001003ff000e03ff807fffff001fffff800f9f80e003e3c03800f0e00f383c3c03ce0f0f9fff03c3fffbc0f0fffcf03e3fff7c3ffe003e1fffc00f07ffffffc1ffffffe00f007ff803c01fff0ff01ffff1fc3ffffe3f3ff80fcfc7f803f0f0000ffc1c0003fe0000007c@00$长安城$1493$34$105","303137,2F3036",173, 40, 285, 76)
    #x,y = blRobot.findMultiColorInRegionFuzzy( 0xef6fdc, "24|5|0xffeecb,-7|30|0x2fb7ff", 90, 0, 0, 1919, 1079)
    end = time.time()
    print("Elapsed (with compilation) = %s" % (end - start))
    
if __name__ == "__main__":
    main()
    
    
    
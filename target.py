import pygame
import threading
import lightgun
import math
import os
import time

COLOR_BACKGROUND = (0,100,0)
COLOR_TARGET_LINES = (200,200,200)
COLOR_TARGET_SCORES = (255,255,255)
COLOR_BULLET = (255,0,0)
COLOR_SCORING = (128,128,128)
FPS = 60
BULLET_SIZE = 0.01
bullets = []
score = 0
target = None       

class Target:
    def __init__(self, circles=10, size=0.4, shots=10):
        self.circles = circles
        self.size = size
        self.shots = shots
        self.spacing = WINDOW_SIZE[1] * 0.5 * self.size / self.circles
        
    def r(self, i):
        if i == -1:
            return 0
        return self.spacing * (i+1)
        
    def score(self,i):
        return self.circles-i
        
    def draw(self):
        for i in range(self.circles):
            r = self.r(i)
            pygame.draw.circle(surface, COLOR_TARGET_LINES, CENTER, int(r), 1)
            drawText("%d" % self.score(i), (CENTER[0],CENTER[1]+r+self.spacing*0.5-self.spacing), self.spacing, COLOR_TARGET_SCORES)
            
    def shoot(self,xy):
        global score
        bullets.append(xy)
        r = math.hypot(xy[0]-CENTER[0],xy[0]-CENTER[0])
        for i in range(self.circles):
            if r <= self.r(i):
                score += self.score(i)
                break
            
def drawText(text, xy, size, color, align="c"):
    rendered = pygame.font.SysFont(FONT,int(size)).render(text, True, color)
    textRect = rendered.get_rect()
    if align.startswith("r"):
        textRect.right = int(xy[0])
        textRect.top = int(xy[1])
    else:
        textRect.center = (int(xy[0]),int(xy[1]))
    surface.blit(rendered, textRect)
            
def getDisplaySize():
    info = pygame.display.Info()
    return info.current_w, info.current_h
    
def scale(y):
    return int(WINDOW_SIZE[1]*y)
        
def getDimensions():
    global WINDOW_SIZE, SCALE, CENTER
    WINDOW_SIZE = surface.get_size()
    CENTER = WINDOW_SIZE[0]//2, WINDOW_SIZE[1]//2
    myfont = pygame.font.SysFont(FONT,scale(0.1))

def ChooseGame():
    drawBoard()
    return Target()
    
def drawScores():
    drawText("Shot %d/%d" % (len(bullets)+1,target.shots), (WINDOW_SIZE[0]-10, scale(0.1)), scale(0.1), COLOR_SCORING, align="r")
    drawText("Score %d" % score, (WINDOW_SIZE[0]-10, scale(0.2)), scale(0.1), COLOR_SCORING, align="r")
    
def drawBoard():
    surface.fill(COLOR_BACKGROUND)
    if target is None:
        return
    drawScores()
    target.draw()
    for bullet in bullets:
        pygame.draw.circle(surface, COLOR_BULLET, bullet, scale(BULLET_SIZE))
    
def PlayGame():
    global bullets
    global score
    
    bullets = []
    score = 0
    
    startTime = time.time()
    running = True

    while running and len(bullets)+1 < target.shots:
        clock.tick(FPS)
        pygame.event.pump()
        for event in pygame.event.get():        
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                running = False
            elif event.type == pygame.VIDEORESIZE:
                surface = pygame.display.set_mode((event.w, event.h),pygame.RESIZABLE)
                getDimensions()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and time.time()-startTime>0.25:
                target.shoot(pygame.mouse.get_pos())
        drawBoard()
        pygame.display.flip()
        
    return running

print("Press 1+2 on Wiimote, ensuring Wii is off.")
lightgun.connect()
t = threading.Thread(target=lightgun.emulateMouse,kwargs={"mouseName":"miniMouse", "rumble":True})
t.daemon = True
t.start()

pygame.init()
pygame.font.init()
FONT = pygame.font.get_default_font()
pygame.key.set_repeat(300,100)
os.environ['SDL_VIDEO_CENTERED'] = '1'
surface = pygame.display.set_mode(getDisplaySize(), pygame.FULLSCREEN)
clock = pygame.time.Clock()

getDimensions()
pygame.display.set_caption("target")

visibleCursor = pygame.mouse.get_cursor()
invisibleCursor = ((8,8),(0,0),(0,0,0,0,0,0,0,0),(0,0,0,0,0,0,0,0))

while True:
    pygame.mouse.set_cursor(*visibleCursor)
    target = ChooseGame()
    if target is None:
        break
    pygame.mouse.set_cursor(*invisibleCursor)
    #pygame.mouse.set_visible(False)
    if not PlayGame():
        break
    time.sleep(5)
        
pygame.quit()


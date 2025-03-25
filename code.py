# 导入必要的库和模块
from adafruit_display_text import label       # 显示文本功能
from adafruit_bitmap_font import bitmap_font  # 位图字体支持
import digitalio                              # 数字输入输出控制
from time import sleep                        # 时间相关函数
from random import randrange                  # 生成随机数
import board                                  # 板级引脚定义
import displayio                              # 显示核心库
import busio                                  # 总线协议支持
import adafruit_imageload                     # 图像加载工具
from adafruit_st7789 import ST7789            # ST7789显示屏驱动

# 初始化显示系统
displayio.release_displays()  # 释放之前可能存在的显示资源

# 配置SPI总线（使用GP10作为SCK，GP11作为MOSI）
spi = busio.SPI(board.GP10, board.GP11)

# 尝试锁定SPI总线（确保通信独占）
while not spi.try_lock():
    print(".")
    pass

spi.configure(baudrate=24_000_000)  # 配置SPI为24MHz高速通信
spi.unlock()  # 释放SPI总线控制权

# 定义显示屏控制引脚
tft_cs = board.GP9   # 片选引脚
tft_dc = board.GP8   # 数据/命令选择引脚

# 创建四线制显示总线（包含复位引脚GP12）
display_bus = displayio.FourWire(
    spi,
    command=tft_dc,
    chip_select=tft_cs,
    reset=board.GP12
)

# 初始化ST7789显示屏（240x135分辨率，特定起始位置，270度旋转）
display = ST7789(
    display_bus,
    width=240,
    height=135,
    rowstart=40,
    colstart=53,
    rotation=270
)

# 配置按钮输入（上、中、下三个按钮）
# 上按钮（GP2，启用内部上拉）
button_up = digitalio.DigitalInOut(board.GP2)
button_up.direction = digitalio.Direction.INPUT
button_up.pull = digitalio.Pull.UP

# 中央按钮（GP3，启用内部上拉）
button_center = digitalio.DigitalInOut(board.GP3)
button_center.direction = digitalio.Direction.INPUT
button_center.pull = digitalio.Pull.UP

# 下按钮（GP18，启用内部上拉）
button_down = digitalio.DigitalInOut(board.GP18)
button_down.direction = digitalio.Direction.INPUT
button_down.pull = digitalio.Pull.UP

# 加载游戏字体文件
font = bitmap_font.load_font("fonts/Junction-regular-24.bdf")

# 创建分数显示标签（橙色文字，定位在左上角(10,10)）
text_score = label.Label(font, text=str(0), color=0xD83C02)
text_score.anchor_point = (0, 0)          # 设置锚点为左上角
text_score.anchored_position = (10, 10)   # 设置显示位置

# 创建显示组并设置为根显示组
group = displayio.Group()
display.root_group = group  # 等效于旧版的display.show(group)

# 加载管道图像资源
pipe_sheet, palette = adafruit_imageload.load(
    "images/pipe.bmp",
    bitmap=displayio.Bitmap,
    palette=displayio.Palette
)
palette.make_transparent(0)  # 设置调色板索引0为透明色

# 创建管道图块网格（尺寸30x135像素，初始位置(80,80)）
pipe = displayio.TileGrid(
    pipe_sheet,
    pixel_shader=palette,
    width=1,
    height=1,
    tile_width=30,
    tile_height=135
)
pipe[0] = 0  # 设置初始图块索引
pipe.y = 80  # Y轴位置
pipe.x = 80  # X轴位置

# 加载游戏结束画面资源
gameover_image, palette = adafruit_imageload.load(
    "images/gameover.bmp",
    bitmap=displayio.Bitmap,
    palette=displayio.Palette
)

# 设置调色板使索引0颜色透明（用于透明背景）
palette.make_transparent(0)

# 创建游戏结束画面的TileGrid对象
gameover = displayio.TileGrid(gameover_image, pixel_shader=palette)
gameover.x = 4  # 水平位置
gameover.y = 32  # 垂直位置

# 游戏状态存储字典
store = {
    'time': 0,      # 游戏时间
    'score': 0,     # 当前得分
    'gameover': False  # 游戏结束标志
}

# 基础精灵类
class Sprite:
    def __init__(self, w, h, x, y, speed, img, transparent=False):
        # 加载图像资源
        sprite_sheet, palette = adafruit_imageload.load(
            img, bitmap=displayio.Bitmap, palette=displayio.Palette)
        
        # 设置透明色（如果需要）
        if transparent:
            palette.make_transparent(0)
        
        # 创建TileGrid对象配置精灵表
        sheet = displayio.TileGrid(
            sprite_sheet,
            pixel_shader=palette,
            width=1, height=1,
            tile_width=w, tile_height=h
        )
        sheet[0] = 0  # 设置初始显示的图块
        
        # 设置初始位置
        sheet.x = x
        sheet.y = y
        
        # 存储属性
        self.sheet = sheet
        self.w = w    # 精灵宽度
        self.h = h    # 精灵高度
        self.x = x    # X坐标
        self.y = y    # Y坐标
        self.speed = speed  # 移动速度
        
        # 将精灵添加到显示组
        group.append(self.sheet)

# 小鸟类（继承自Sprite）
class Bird(Sprite):
    def __init__(self):
        super().__init__(46, 32, 20, 20, 3, 'images/bird.bmp', True)
        self.current = 0    # 当前动画帧
        self.jump = False   # 跳跃状态标志
        self.toy = 135 - self.h  # 跳跃目标Y坐标
    
    # 处理飞行动画
    def fly(self, time):
        if time % 100 == 0:  # 每100帧切换动画
            self.current += 1
            if self.current == 2:
                self.current = 0
        self.sheet[0] = self.current  # 更新显示帧
    
    # 更新小鸟状态
    def update(self, time):
        self.fly(time)  # 更新动画
        
        # 检测跳跃按钮按下
        if button_up.value == 0:
            if not self.jump:
                self.toy = self.y - self.h  # 设置跳跃目标
                self.jump = True
        
        # 每30帧更新位置
        if time % 30 == 0:
            if self.jump:
                self.y -= self.speed  # 向上移动
                if self.y <= 0:       # 顶部边界检测
                    self.y = 0
                    self.jump = False
                if self.y <= self.toy:  # 到达跳跃目标
                    self.toy = 135 - self.h
                    self.jump = False
            else:
                self.y += self.speed  # 重力下落
                if self.y > 135 - self.h:  # 底部边界检测
                    self.y = 135 - self.h
        
        self.sheet.y = self.y  # 更新显示位置

# 背景类（继承自Sprite）
class Background(Sprite):
    def __init__(self, x):
        super().__init__(240, 135, x, 0, 1, 'images/bg.bmp')
    
    def update(self, time):
        if time % 150 == 0:  # 每150帧滚动背景
            self.x -= self.speed
            self.sheet.x = self.x
            if self.x <= -240:  # 循环背景
                self.x = 240

# 初始化背景和角色
bg1 = Background(0)    # 左半背景
bg2 = Background(240)  # 右半背景
bird = Bird()          # 创建小鸟实例

# 管道类（继承自Sprite）
class Pipe(Sprite):
    def __init__(self, x, y, img, t):
        super().__init__(30, 135, x, y, 1, img)
        self.t = t  # 管道类型标识
    
    def update(self, time):
        if time % 15 == 0:  # 每15帧移动管道
            self.x -= self.speed
            if self.x < -30:  # 管道移出屏幕后重置
                self.x = 240
                store['score'] += 1  # 得分增加
                text_score.text = str(store['score'])  # 更新得分显示
                
                # 随机生成新位置
                if self.t == 'a':
                    self.y = randrange(50, 120, 20)
                else:
                    self.y = randrange(-120, -50, 20)
                self.sheet.y = self.y
            
            # 碰撞检测（小鸟与管道）
            # 检测左上角碰撞
            if bird.x > self.x and bird.x < (self.x + self.w):
                if bird.y > self.y and bird.y < (self.y + self.h):
                    group.append(gameover)
                    store['gameover'] = True
            
            # 检测右下角碰撞
            if (bird.x + bird.w) > self.x and (bird.x + bird.w) < (self.x + self.w):
                if (bird.y + bird.h) > self.y and (bird.y + bird.h) < (self.y + self.h):
                    group.append(gameover)
                    store['gameover'] = True

# 创建管道实例
pipe1 = Pipe(240, 50, 'images/pipe.bmp', 'a')   # 下方管道
pipe2 = Pipe(380, -50, 'images/pipe2.bmp', 'b') # 上方管道

# 将得分文本添加到显示组
group.append(text_score)

# 主游戏循环
while True:
    if not store['gameover']:
        store['time'] += 1  # 更新时间计数器
        # 更新所有游戏对象
        bird.update(store['time'])
        bg1.update(store['time'])
        bg2.update(store['time'])
        pipe1.update(store['time'])
        pipe2.update(store['time'])
    else:
        # 游戏结束状态处理
        if button_down.value == 0:  # 检测重新开始按钮
            group.remove(gameover)  # 移除结束画面
            # 重置管道位置
            pipe1.x = 240
            pipe2.x = 380
            # 重置游戏状态
            store['score'] = 0
            store['gameover'] = False
            text_score.text = str(store['score'])  # 重置得分显示
 
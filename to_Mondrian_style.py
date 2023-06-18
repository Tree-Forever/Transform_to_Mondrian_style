from typing import *
from PIL import Image, ImageColor
from collections import namedtuple
import random

# A Square box, identified by its corner coordinates
Box = namedtuple('Box', ['Top', 'Bottom', 'Left', 'Right'])
       
# Maximum points that will be sampled in a box.
maxSample = 100

# Computes number of points to sample in a box.
def sampler(box:Box):
    width = abs(box.Left - box.Right + 1)
    height = abs(box.Top - box.Bottom + 1)
    return min(width * height, maxSample)

# Compute the "average" color of a box, 
# by sampling random points in it.
def average(img:Image.Image, rng:random.Random, box:Box):
    sampleSize = sampler(box)
    minx = min(box.Left, box.Right)
    maxx = max(box.Left, box.Right)
    miny = min(box.Top, box.Bottom)
    maxy = max(box.Top, box.Bottom)

    sample = []
    for i in range(sampleSize):
        x = rng.randint(minx, maxx)
        y = rng.randint(miny, maxy)
        sample.append(img.getpixel((x, y)))

    red = sum(pix[0] for pix in sample) / len(sample)
    green = sum(pix[1] for pix in sample) / len(sample)
    blue = sum(pix[2] for pix in sample) / len(sample)

    return red, green, blue

# Computes the "distance" between 2 colors.
def distance(color1, color2):
    r1, g1, b1 = color1
    r2, g2, b2 = color2
    return (r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2

# Split a box into 2 parts, by attempting
# random splits and taking the split that
# maximizes color difference between the areas.
def split(img:Image.Image, rng:random.Random, cuts, margin, box:Box):
    # Construct a list of possible box splits
    attempts = []
    # Constructs random vertical cuts.
    minx = min(box.Left, box.Right)
    maxx = max(box.Left, box.Right)
    if minx + margin < maxx - margin:
        for i in range(cuts):
            cut = rng.randint(minx + margin, maxx + 1 - margin)
            box1 = box._replace(Right=cut)
            box2 = box._replace(Left=cut + 1)
            attempts.append((box1, box2))

    # Construct random horizontal cuts.
    miny = min(box.Top, box.Bottom)
    maxy = max(box.Top, box.Bottom)
    if miny + margin < maxy - margin:
        for i in range(cuts):
            cut = rng.randint(miny + margin, maxy + 1 - margin)
            box1 = box._replace(Top=cut)
            box2 = box._replace(Bottom=cut + 1)
            attempts.append((box1, box2))

    # Extract the cut with largest color difference,
    # if a successful cut has been found.
    if attempts:
        return max(attempts, key=lambda pair: distance(average(img, rng, pair[0]), average(img, rng, pair[1])))
    else:
        return None

# Given a current division of image into boxes,
# create next generation by splitting a random Box 
# from the current Boxes.
def spawn(rng:random.Random, splitter:callable, boxes:List[Box]):
    count = len(boxes)
    boxIndex = rng.randint(0, count - 1)
    
    new_boxes = []
    for i in range(count):
        if i == boxIndex:
            split_result = splitter(boxes[i])
            if split_result is None:
                new_boxes.append(boxes[i])
            else:
                box1, box2 = split_result
                new_boxes.append(box1)
                new_boxes.append(box2)
        else:
            new_boxes.append(boxes[i])
    
    return new_boxes

# Recursively create boxes that cover the starting image
def boxize(img:Image.Image, rng:random.Random, cuts, margin, depth:int):
    width = img.width
    height = img.height
    box = Box(Left=0, Right=width-1, Top=height-1, Bottom=0)
    splitter = lambda b: split(img, rng, cuts, margin, b)
    
    def fragment(boxes, gen):
        if gen >= depth:
            return boxes
        else:
            more_boxes = spawn(rng, splitter, boxes)
            return fragment(more_boxes, gen + 1)
    
    return fragment([box], 0)

# Measure whiteness (the higher r,g,b, the whiter).
def whiteness(color:Tuple[float, float, float]):
    r, g, b = color
    return min(r, g, b)
# Round value to the closest multiple of grain .
def roundize(value, grain):
    value = int(grain * round(value / grain))
    if value > 255:
        return 255
    else:
        return value
# Create a simplified RGB color, using restricted palette.
def contrastize(grain, color:Tuple[float, float, float]):
    r, g, b = color
    r = roundize(r, grain)
    g = roundize(g, grain)
    b = roundize(b, grain)
    return (r, g, b)
# Paint each box based on its average color.
# A proportion of the clearest boxes are painted pure white. 
def colorize(img:Image.Image, rng:random.Random, white:float, contrast:float, boxes:List[Box]):
    count = len(boxes)
    whitened = int(white * count)
    colors = []
    
    for i, box in enumerate(boxes):
        avg_color = average(img, rng, box)
        if i < whitened:
            colors.append((box, (255, 255, 255)))  # Pure white
        else:
            colors.append((box, contrastize(contrast, avg_color)))
    
    for box, color in colors:
        for x in range(box.Left, box.Right + 1):
            for y in range(box.Bottom, box.Top + 1):
                pixel = img.getpixel((x, y))
                img.putpixel((x, y), color)
    
    return img

# Paint the black borders around each Box.
def borderize(img:Image.Image, margin:int, boxes:List[Box]):
    width = img.width
    height = img.height
    
    def borders(box):
        if margin > 0:
            if box.Bottom > 0:
                for x in range(box.Left, box.Right + 1):
                    for m in range(margin + 1):
                        yield (x, box.Bottom + m)
            if box.Top < (height - 1):
                for x in range(box.Left, box.Right + 1):
                    for m in range(margin + 1):
                        yield (x, box.Top - m)
            if box.Left > 0:
                for y in range(box.Bottom, box.Top + 1):
                    for m in range(margin + 1):
                        yield (box.Left + m, y)
            if box.Right < width - 1:
                for y in range(box.Bottom, box.Top + 1):
                    for m in range(margin + 1):
                        yield (box.Right - m, y)
    
    for box in boxes:
        for x, y in borders(box):
            img.putpixel((x, y), (0, 0, 0))  # Black
    
    return img

# Utilities to determine adequate black margin width
def marginWidth(width, height):
    return min(width, height) // 200

# Utility to determine adequate minimum box edge
def minWidth(width, height):
    borders = 2 * marginWidth(width, height)
    edge = min(width, height) // 10
    return max(edge, borders)

def main(source_file,target_file):
    # # Replace the image path by something adequate...
    # source_file = 'test.jpg'
    # target_file = "Mondrianized.png"
    
    image = Image.open(source_file)
    width, height = image.size
    margin = marginWidth(width, height)
    edges = minWidth(width, height)

    # cuts = 10  # random cuts attempted at each step
    # depth = 50  # "search" depth
    # white = 0.4  # proportion of boxes rendered white
    # contrast = 32.0  # rounding factor to simplify colors
    
    # 在split函数中把画面分割成 cuts*cuts 个方格
    # 选择具有最大颜色差异的切割方式，构建切割器splitter
    #次数越多，切割样式越复杂
    cuts = 100           # int >0    
    # 在fragment函数中使用spawn函数调用splitter切割器
    # 进行切割方框的次数    
    # #次数越多，画面越复杂
    depth = 50          # int >0    
    # 白色方框的比例
    white = 0.1         # float [0, 1]
    # rgb只能为contrast的倍数。值越大，颜色越简单。
    contrast = 32.0     # float (0, 255//2)

    rng = random.Random()

    boxes = boxize(image, rng, cuts, edges, depth)
    colorized = colorize(image, rng, white, contrast, boxes)
    borderized = borderize(colorized, margin, boxes)

    borderized.save(target_file, "PNG")

    print("Done")

if __name__ == "__main__":
    source_file = '.\\test.jpg'
    target_file = '.\\Mondrianized.png'
    main(source_file,target_file)
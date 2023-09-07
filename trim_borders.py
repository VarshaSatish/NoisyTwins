import os
from PIL import ImageFile, Image, ImageChops
ImageFile.LOAD_TRUNCATED_IMAGES = True

def trim(im):
    bg = Image.new(im.mode, im.size, im.getpixel((0, 0)))
    try:
        diff = ImageChops.difference(im, bg)
        diff = ImageChops.add(diff, diff, 2.0, 0)
        bbox = diff.getbbox()
        im_trim = im.crop(bbox)
        if bbox:
            return im_trim.crop((1,1,369,369))
        else:
            return trim(im.convert("RGB"))
    except:
        return im
    
rootdir = "/home/test/varsha/images/generated_samples_untrimmed/"
dstdir = '/home/test/varsha/images/generated_samples_368_368/'
os.makedirs(dstdir, exist_ok=True)
# l = 0
# size = (128,128)
for subdir, dirs, files in os.walk(rootdir):
    # print(subdir, dirs)
    for file in files[:10]:
        print(file)
        im = Image.open("{}/{}".format(subdir, file))
        # im_trim = im.resize(size, resample=0) 
        im_trim = trim(im)
        # print(im_trim.size)
        dst = subdir.replace('generated_samples_untrimmed', 'generated_samples_368_368')
        # print(dst)
        os.makedirs(dst, exist_ok=True)
        im_trim.save("{}/{}".format(dst, file))
        # l += 1
    #     exit()
    # exit()
# print(l)
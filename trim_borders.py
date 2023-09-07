import os
from PIL import ImageFile, Image, ImageChops
ImageFile.LOAD_TRUNCATED_IMAGES = True

def trim(im):
    bg = Image.new(im.mode, im.size, im.getpixel((0, 0)))
    try:
        diff = ImageChops.difference(im, bg)
        # diff = ImageChops.add(diff, diff, 2.0, 0)
        bbox = diff.getbbox()
        im_trim = im.crop(bbox)
        if bbox:
            return im_trim.crop((1,1,369,369))
        else:
            return trim(im.convert("RGB"))
    except:
        return im
    
rootdir = "/home/test/varsha/images/generated_samples_368_368/"
dstdir = '/home/test/varsha/images/generated_samples_new/'
os.makedirs(dstdir, exist_ok=True)

size = (64,64)
for subdir, dirs, files in os.walk(rootdir):
    for file in files[:10]:
        print(file)
        im = Image.open("{}/{}".format(subdir, file))
        im_trim = trim(im)
        dst = subdir.replace('generated_samples_untrimmed', 'generated_samples_new')
        os.makedirs(dst, exist_ok=True)
        im_trim.save("{}/{}".format(dst, file))
        print(im_trim.size)

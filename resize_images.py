import os
from PIL import ImageFile, Image, ImageChops
ImageFile.LOAD_TRUNCATED_IMAGES = True
    
rootdir = "/home/test/varsha/images/generated_samples_368_368/"
dstdir = '/home/test/varsha/images/generated_samples_128_128_Lanczos/'
os.makedirs(dstdir, exist_ok=True)
# l = 0
# size = (64,64)
size = (128, 128)
for subdir, dirs, files in os.walk(rootdir):
    # print(subdir, dirs)
    for file in files[:10]:
        print(file)
        im = Image.open("{}/{}".format(subdir, file))
        im_trim = im.resize(size, resample=Image.Resampling.LANCZOS) 
        
        # print(im_trim.size)
        dst = subdir.replace('generated_samples_368_368', 'generated_samples_128_128_Lanczos')
        # print(dst)
        os.makedirs(dst, exist_ok=True)
        im_trim.save("{}/{}".format(dst, file))
        print(im_trim.size)
        # l += 1
    #     exit()
    # exit()
# print(l)
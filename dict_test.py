import sys
import math
import pickle

# dict/lookup = 11741073 469.33 MB

def convert_size(size_bytes):
   if size_bytes == 0:
       return "0B"
   size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
   i = int(math.floor(math.log(size_bytes, 1024)))
   p = math.pow(1024, i)
   s = round(size_bytes / p, 2)
   return "%s %s" % (s, size_name[i])


count = 0
lookup = {}
with open('/Volumes/UsedGlum/naco/names.madsrdf.nt') as infile:

	for line in infile:


		if '# BEGIN' in line:
			lccn = line.split('/')[-1].strip()
	


		if '<http://www.loc.gov/mads/rdf/v1#authoritativeLabel>' in line and lccn in line:
			label = line.split('> "')[1].strip()[:-3]

			lookup[label] = lccn
			count=count+1

			if count % 10000 == 0:
				print(len(lookup), convert_size(sys.getsizeof(lookup)))

print(len(lookup), convert_size(sys.getsizeof(lookup)))
with open('/Volumes/UsedGlum/naco/dict_names.pickle', 'wb') as handle:
	pickle.dump(lookup, handle, protocol=pickle.HIGHEST_PROTOCOL)

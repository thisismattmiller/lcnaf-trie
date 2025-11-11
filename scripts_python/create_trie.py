import sys
import math
import marisa_trie
import string
import unicodedata
import re
import pickle

# trie = marisa_trie.Trie()

# print(trie.set('hello'))

# # dict/lookup = 11741073 469.33 MB

known_prefixes = {'nb':'1', 'nn':'2', 'no':'3', 'nr':'4', 'ns':'5', 'n':'6'}


def convert_size(size_bytes):
   if size_bytes == 0:
       return "0B"
   size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
   i = int(math.floor(math.log(size_bytes, 1024)))
   p = math.pow(1024, i)
   s = round(size_bytes / p, 2)
   return "%s %s" % (s, size_name[i])


latin_letters= {}

def is_latin(uchr):
    try: return latin_letters[uchr]
    except KeyError:
         return latin_letters.setdefault(uchr, 'LATIN' in unicodedata.name(uchr))

def only_roman_chars(unistr):
    return all(is_latin(uchr)
           for uchr in unistr
           if uchr.isalpha()) # isalpha suggested by John Machin




count = 0
all_keys = []
all_lccn = []
all_lccn_prefix = {}
norm_dupe = {}
lookup=[]
with open('/Volumes/UsedGlum/naco/names.madsrdf.nt') as infile:

	for line in infile:


		if '# BEGIN' in line:
			lccn = line.split('/')[-1].strip()
			if '-' in lccn:
				# do not use the internal indriect geo headings
				lccn = "SKIP-SKIP-SKIP"

			for p in known_prefixes:
				if lccn.startswith(p):
					lccn_new = lccn.replace(p,known_prefixes[p])
					try:
						lccn_new = int(lccn_new)
					except:
						lccn_new = lccn

					break

			# print("lccn_new",lccn_new)


	
		if '<http://www.loc.gov/mads/rdf/v1#authoritativeLabel>' in line and lccn in line:

			# TODO Test for non-latin here
			
			label = line.split('> "')[1].strip()[:-3]
			norm = label.translate(str.maketrans('', '', string.punctuation))
			norm = unicodedata.normalize('NFKD', norm).encode('ascii', 'ignore').decode("utf-8")
			norm = norm.lower().replace(' ','')
			norm = ''.join(sorted(norm))
			lookup.append(None)

			try:
				s =  re.search(r"[a-z]", norm).start()
			except:
				print("No letters:", label, "|", norm)
				s = 0
		
			first_part = norm[:s]
			second_part = norm[s:]
			norm = second_part + first_part


			if norm in norm_dupe:
				norm_dupe[norm].append({'label': label, 'lccn_new':lccn_new})
			else:
				norm_dupe[norm] = [{'label': label, 'lccn_new':lccn_new}]

			count=count+1
			all_keys.append(norm)
			all_lccn.append(lccn)
			if count % 500000 == 0:
				print(count)
				# print(len(trie), convert_size(sys.getsizeof(trie)))
				# trie.save('/Volumes/UsedGlum/naco/trie.marisa')


				# print(len(lookup), convert_size(sys.getsizeof(lookup)))


trie = marisa_trie.Trie(all_keys)
print('trie length',len(trie))
trie.save('/Volumes/UsedGlum/naco/trie.marisa')

# for idx, k in enumerate(norm_dupe):
# 	print(idx,k)


for x in trie:
	pos = trie[x]
	if len(norm_dupe[x]) == 1:
		lookup[pos] = norm_dupe[x][0]['lccn_new']
	else:		
		lookup[pos] = norm_dupe[x]

with open('/Volumes/UsedGlum/naco/trie_lookup.pickle', 'wb') as handle:
	pickle.dump(lookup, handle, protocol=pickle.HIGHEST_PROTOCOL)



# print(all_lccn_prefix)

# print(len(lookup), convert_size(sys.getsizeof(lookup)))
# with open('/Volumes/UsedGlum/naco/dict_names.pickle', 'wb') as handle:
# 	pickle.dump(lookup, handle, protocol=pickle.HIGHEST_PROTOCOL)

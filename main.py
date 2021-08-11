# Which update feed to query updates from? 'Base'/'SO'
FEED = 'Base'
# Version prefix is automatically set to 'EX1' for the SO feed. Set it here for Base.
PREFIX = 'U33'
# Number of most recent items to process from the feed.
LATEST_N = 5


from html.parser import HTMLParser
import urllib.request as req
import re
import json


class InfoParser(HTMLParser):
	def __init__(self):
		super().__init__()
		self.result = []
		self.listDepth = 0
		self.headerList = []
		self.headerDepth = 0
		self.buffer = ''
		self.version = '000000'
		self.inArticle = self.italic = self.bold = self.header = self.link = self.p = False
		self.imgCount = 0
		self.videoCount = 0

	def handle_starttag(self, tag, attrs):
		#if tag == 'article':
		#	self.inArticle = True
		#	return
		if not self.inArticle:
			return
		if tag == 'p':
			self.p = True
			return
		if tag == 'ul' and len(attrs) == 0:
			self.listDepth += 1
			return
		if tag == 'li' and self.listDepth:
			self.write('\n' + '*' * self.listDepth + ' ')
			return
		if tag == 'strong' or tag == 'b':
			self.bold = True
			return
		if tag == 'em':
			self.italic = True
			return
		if tag == 'span' and len(attrs) > 0:
			match = re.search(r'font-size:(\d{2})px', attrs[0][1])
			if match:
				level = match.group(1)
				if not self.headerList.count(level):
					self.headerList.append(level)
				self.headerDepth = self.headerList.index(level)
				self.header = True
			return
		if tag == 'a':
			self.link = attrs[0][1]
			return
		if tag == 'img':
			self.imgCount += 1
			self.result.append(
				'\n[[File:' + PREFIX + '-' + self.version + '-' + str(self.imgCount) + '.png]]\n')
			return
		if tag == 'video':
			self.videoCount += 1
			self.result.append(
				'\n[[File:' + PREFIX + '-' + self.version + '-' + str(self.videoCount) + '.mp4]]\n')
			return

	def handle_endtag(self, tag):
		if not self.inArticle:
			return
		if tag == 'section':
			self.inArticle = False
			return
		if tag == 'p':
			self.flushBuffer()
			self.p = False
			return
		if tag == 'ul':
			self.listDepth -= 1
			self.flushBuffer()
			if self.listDepth == 0:
				self.result.append('\n')
			return
		if tag == 'strong' or tag == 'b':
			self.bold = False
			return
		if tag == 'em':
			self.italic = False
			return
		if tag == 'span':
			self.header = False
			return
		if tag == 'a':
			self.link = None
			return

	def handle_data(self, data):
		if self.inArticle:
			data = data.replace('\n', '').replace('\t', '').replace('\xa0', ' ')
			if data == ' ':
				return
			if len(data) > 0 and self.inArticle:
				if self.header:
					self.write('===' + '=' * self.headerDepth + ' ')
				else:
					if self.bold:
						self.write("'''")
					if self.italic:
						self.write("''")
					if self.link:
						self.write('[' + self.link + ' ')
				self.write(data)
				if self.header:
					self.write(' ' + '=' * self.headerDepth + '===')
				else:
					if self.link:
						self.write(']')
					if self.italic:
						self.write("''")
					if self.bold:
						self.write("'''")
		else:
			match = re.search(r'Game Update.*(\d{6})', data)
			if match:
				self.version = match.group(1)
			if data == 'Update Information:':
				self.inArticle = True
				return
	
	def write(self, text):
		self.buffer += text

	def flushBuffer(self):
		if self.buffer:
			if self.p:
				self.result.append('\n')
			self.buffer = self.buffer.replace("''''''''", "''"
				).replace("'''''''", "'''"
				).replace("''''''",''
				).replace("''''", ''
            	).replace("’", "'"
                ).replace("‘", "'"
				).replace("“", '"'
				).replace("”", '"')
			header = re.match("'''([\w ]+)'''", self.buffer)
			if header:
				if not self.headerList.count("'''"):
					self.headerList.append("'''")
				self.headerDepth = self.headerList.index("'''")
				self.buffer = '===' + '=' * self.headerDepth + ' ' + \
					header.group(1) + ' ' + '=' * self.headerDepth + '==='
			self.result.append(self.buffer)
			if self.p:
				self.result.append('\n')
			self.buffer = ''

class IndexParser(HTMLParser):
	def __init__(self):
		super().__init__()
		self.result = []
		self.index = 0
		self.inRow = False
		self.inHeader = False
		self.isHotfix = False

	def handle_starttag(self, tag, attrs):
		if tag == 'li' and attrs.count(('class', 'cCmsRecord_row ')):
			self.result.append(dict())
			self.inRow = True
			return
		if tag == 'h3':
			self.inHeader = True
			return
		if tag == 'i' and attrs.count(('class', 'fa fa-warning')):
			self.isHotfix = True
			return
		if tag == 'a':
			if attrs.count(('rel', 'next')):
				self.cont = attrs[0][1]
				return
			for attr in attrs:
				if attr[1] and attr[1].find('cRelease') != -1:
					self.result[self.index]['url'] = attrs[0][1]
			return


	def handle_endtag(self, tag):
		if self.inRow and tag == 'li':
			self.index += 1
			self.inRow = False
			self.isHotfix = False
			return
		if self.inHeader and tag == 'h3':
			self.inHeader = False
			return

	def handle_data(self, data):
		if self.inRow:
			if self.inHeader:
				version = re.search(r'\d{6}', data)
				if version:
					self.result[self.index]['build'] = int(version.group(0))
				if data == 'Test':
					self.result[self.index]['type'] = 'Test'
				elif data == 'Release':
					if self.isHotfix:
						self.result[self.index]['type'] = 'Hotfix'
					else:
						self.result[self.index]['type'] = 'Release'
				return
			date = re.search(r'Released ([\d/]*)', data)
			if date:
				self.result[self.index]['release'] = date.group(1)
				return

def returnBuildNum(update):
	return update['build']

def getPhraseMap():
	global phraseMap 
	if phraseMap is None:
		with open('phrasemap.json') as file:
			map = json.load(file)
		phraseMap = dict(sorted(map.items()))
	return phraseMap

def filterKeys(phrase, keys):
	sample = phrase.split()
	# Only matches to the end of 'phrase', the rest of the key is ignored
	matches = [x for x in keys if sample == x.split()[0:len(sample)]]
	# Return string on exact match
	if len(matches) == 0:
		return None
	if len(matches) == 1 and matches[0] == phrase:
		return matches[0]
	return matches

def removeDuplicate(lst):
	seen = set()
	result = []
	for i in lst:
		if i in seen:
			continue
		else:
			result.append(i)
			seen.add(i)
	return result

def searchPhrases(text):
	map = getPhraseMap()
	text = text.replace('.', ''
		).replace('!', ''
		).replace('?', ''
		).replace(',', ''
		).replace(';', ''
		).replace(':', ''
        ).replace("'", ''
        ).replace('"', ''
		).replace('(', ''
		).replace(')', '')
	text = text.lower()
	words = text.split()
	# Oredered results for easier checking. Must remove duplicates at the end.
	result = list()
	myRange = iter(range(0, len(words)))
	for i in myRange:
		keys = map.keys()
		word = words[i]
		# Recursively match with lengthening phrase until exact match (when a string is returned). A longer match is preferred, which makes phrase exclusion possible. (Phrase mapped to an empty array.)
		while True:
			matches = filterKeys(word, keys)
			if type(matches) is list:
				if i + 1 < len(words):
					wordCount = len(word.split())
					keys = matches
					word += ' ' + words[i + wordCount]
				else:
					match = None
					break			
			else:
				match = matches
				break
		if match:
			result.extend(map[match])
			# Skip extra words, if the match was longer than one word. This is necessary to use phrase maps for phrase exclusion
			for j in range(0, len(match.split()) - 1):
				next(myRange)
	result = removeDuplicate(result)
	return ', '.join(result)

def getIndex(url):
	with req.urlopen(url) as source:
			response = source.read().decode('utf-8')
	return response

def getData(url):
	info = getIndex(url)
	parser = InfoParser()
	parser.feed(info)
	return ''.join(parser.result)

def getLatest(n, feed):
	global PREFIX
	if feed == 'SO':
		url = 'https://forums.kleientertainment.com/game-updates/oni-so/'
		PREFIX = 'EX1'
	else:
		url = 'https://forums.kleientertainment.com/game-updates/oni-alpha/'
	parser = IndexParser()
	# An extra item is need to determine 'prev' attribute.
	while len(parser.result) < n + 1:
		index = getIndex(url)
		parser.feed(index)
		url = parser.cont
	latest = parser.result
	# Latest release is pinned to the top, so sorting is necessary. ASC, latest last
	latest.sort(key = returnBuildNum)
	latest = latest[-n - 1:]
	for item in latest:
		i = latest.index(item)
		if i == 0:
			continue
		prev = PREFIX + '-' + str(latest[i - 1]['build'])
		if i == len(latest) - 1:
			next = ''
		else:
			next = PREFIX + '-' + str(latest[i + 1]['build'])
		item['data'] = getData(item['url'])
		relnotes = re.search(r'((?:oni-so|oni-alpha)/.*)/', item['url']).group(1)
		affected = searchPhrases(item['data'])
		out = f'''{{{{VersionInfoHeader{"""
| expansion = Spaced Out!""" if feed == 'SO' else ''}
| date = {item['release']}
| contentBase = {'no' if feed == 'SO' else 'yes'}
| contentSO = yes
| relnotes = {relnotes}
| type = {item['type']}
| prev = {prev}
| next = {next}
| name = 
| affectedPages = {affected}
}}}}

== Update Information ==
'''
		item['out'] = out + item['data'] + '\n{{VersionInfoFooter}}'
	return latest[1:n+1]


phraseMap = None
result = getLatest(LATEST_N, FEED)
print('start\n', str(result))
for update in result:
	with open('out/' + str(update['build']) + '.txt', 'w') as file:
		file.write(update['out'])

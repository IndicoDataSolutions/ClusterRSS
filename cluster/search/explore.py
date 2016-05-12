import json
import os, sys
import indicoio
import operator

from .client import ESConnection
from .schema import Document, INDEX
from load_data import upload_data, add_indico

import concurrent.futures
indicoio.config.api_key = 'fb039b9dafb34eeb83aa3307e8efb167'

def load_data(filename):
	with open(filename, 'rb') as f:
		return [json.loads(l) for l in f]

def write_to_files(data, data_dir, chunk_size=500, left_bound=0, right_bound=None):
	right_bound = len(data) if not right_bound else right_bound

	for i in xrange(chunk_size, right_bound, chunk_size):
		print "current spot", left_bound, 'to', i
		with open(data_dir+str(left_bound)+'-'+str(i)+'-lines.ndjson', 'w') as data_dump:
			[data_dump.write(json.dumps(document)+'\n') for document in data[left_bound:i]]
			left_bound = i

	if left_bound < len(data):
		print "finishing up", left_bound, "to", len(data)
		with open(data_dir+str(left_bound)+'-'+str(right_bound)+'-lines.ndjson', 'w') as data_dump:
			[data_dump.write(json.dumps(document)+'\n') for document in data[left_bound:]]


if __name__ == "__main__":
	print "LET'S DO THIS LEEEEEEERROOOOOOOYYYY"
	data_dir = '../../complete/'
	data_dir = os.path.join(os.path.dirname(__file__), data_dir)
	
	# data = load_data(os.path.join(os.path.dirname(__file__), '../../stocks_news.ndjson.txt'))
	# write_to_files(data, data_dir, chunk_size=200)

	sorted_filenames = sorted(os.listdir(data_dir), key=lambda fname: int(fname.split('-')[0]))
	print len(sorted_filenames)
	
	# some_json = []
	# for file in sorted_filenames[0:1]:
	# 	some_json = load_data(data_dir+file)

	# with open('0-9-lines.ndjson', 'w') as r:
	# 	[r.write(json.dumps(line)+'\n') for line in some_json[:10]]

	# with open('../complete/0-9-lines.ndjson', 'r') as r:
	# 	some_json = [json.loads(line) for line in r.readlines()]

	# for fname in sorted_filenames[12:25]:
	# 	with open(os.path.join(data_dir, '../complete/', fname), 'r') as f:
	# 		es.upload([json.loads(l) for l in f.readlines()])
	
	# es = ESConnection("localhost:9200", index='indico-cluster-data-clean')
	left = int(sys.argv[1])
	right = int(sys.argv[2])
	for fname in sorted_filenames[left: right]:
		print fname
		try:
			documents = upload_data(data_dir, fname)
			# es.upload(documents)
		except Exception as exc:
			print '\n\n', fname, 'BROKE BROKE BROKE\n\n'
			import traceback; traceback.print_exc()

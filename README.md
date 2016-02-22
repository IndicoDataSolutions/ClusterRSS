# SentimentComparison

Setup
------

```bash
sudo apt-get install python-numpy python-scipy
sudo pip install numpy scipy
python setup.py develop
python -m indicluster.models # generate sqlite db
# Add INDICO_API_KEY to ~/.bashrc

You'll then need to the phantomjs binary to `/usr/local/bin/phantomjs`.  See the [phantomjs website](http://phantomjs.org/download.html) for download links. After downloading, simply untar and copy `./bin/*` to `/usr/local/bin`/

```


Running
-------
```bash
python -m indicluster.app
# navigate to localhost:8002 in your browser
```

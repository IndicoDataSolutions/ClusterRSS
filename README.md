# SentimentComparison

Setup
------

```bash
sudo apt-get install python-numpy python-scipy
sudo pip install numpy scipy
python setup.py develop
python -m indicluster.models # generate sqlite db
# Add INDICO_API_KEY to ~/.bashrc
```


Running
-------
```bash
python -m indicluster.app
# navigate to localhost:8002 in your browser
```

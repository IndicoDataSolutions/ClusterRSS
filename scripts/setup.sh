sudo apt-get update
sudo apt-get install -y git python-pip python-numpy python-scipy
sudo apt-get install -y libxml2-dev libxslt-dev python-dev lib32z1-dev
sudo apt-get install -y libjpeg-dev libpng-dev zlib1g-dev
sudo pip install scikit-learn requests gevent newspaper SQLAlchemy tornado elasticsearch picklable-itertools sumy selenium feedparser indicoio futures pyexcel pyexcel-xlsx
sudo apt-get install -y tmux

# Requests SSL
sudo apt-get install -y libffi-dev
sudo pip install 'requests[security]'

# Elasticsearch requires JRE
sudo apt-get install -y openjdk-7-jre

# Installing NLTK packages
python -c "import nltk; nltk.download('punkt')"

# Get Github Package
git config --global user.email "contact@indico.io"
git config --global user.name "indico"
git clone https://$GITHUB_ACCESS_TOKEN@github.com/IndicoDataSolutions/ClusterRSS.git
cd ClusterRSS
sudo python setup.py develop

# Get AWS data
sudo apt-get install -y awscli
aws s3 cp --recursive s3://corpii/Finance inputxl

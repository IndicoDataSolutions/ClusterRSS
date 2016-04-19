# encoding:utf-8
# Summarizer
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer as Summarizer
from sumy.nlp.stemmers import Stemmer
from sumy.utils import get_stop_words

class Summary(object):
    LANGUAGE = "english"
    SENTENCES_COUNT = 8 # don't know what number this should be

    def __init__(self, language=LANGUAGE):
        stemmer = Stemmer(language)
        self.summarizer = Summarizer(stemmer)
        self.summarizer.stop_words = get_stop_words(language)
        self.tokenizer = Tokenizer(language)

    def parse(self, text, sentences=SENTENCES_COUNT):
        parser = PlaintextParser(text, self.tokenizer)
        return " ".join(map(
            lambda x: x.__str__(),
            self.summarizer(parser.document, sentences)
        ))

if __name__ == "__main__":
    test_text = """
    Throughout its long history, Earth has warmed and cooled time and again. Climate has changed when the planet received more or less sunlight due to subtle shifts in its orbit, as the atmosphere or surface changed, or when the Sun’s energy varied. But in the past century, another force has started to influence Earth’s climate: humanity
How does this warming compare to previous changes in Earth’s climate? How can we be certain that human-released greenhouse gases are causing the warming? How much more will the Earth warm? How will Earth respond? Answering these questions is perhaps the most significant scientific challenge of our time.
What is Global Warming?
Global warming is the unusually rapid increase in Earth’s average surface temperature over the past century primarily due to the greenhouse gases released as people burn fossil fuels. The global average surface temperature rose 0.6 to 0.9 degrees Celsius (1.1 to 1.6° F) between 1906 and 2005, and the rate of temperature increase has nearly doubled in the last 50 years. Temperatures are certain to go up further.
Earth’s natural greenhouse effect
Earth’s temperature begins with the Sun. Roughly 30 percent of incoming sunlight is reflected back into space by bright surfaces like clouds and ice. Of the remaining 70 percent, most is absorbed by the land and ocean, and the rest is absorbed by the atmosphere. The absorbed solar energy heats our planet.
As the rocks, the air, and the seas warm, they radiate “heat” energy (thermal infrared radiation). From the surface, this energy travels into the atmosphere where much of it is absorbed by water vapor and long-lived greenhouse gases such as carbon dioxide and methane.
When they absorb the energy radiating from Earth’s surface, microscopic water or greenhouse gas molecules turn into tiny heaters— like the bricks in a fireplace, they radiate heat even after the fire goes out. They radiate in all directions. The energy that radiates back toward Earth heats both the lower atmosphere and the surface, enhancing the heating they get from direct sunlight.
This absorption and radiation of heat by the atmosphere—the natural greenhouse effect—is beneficial for life on Earth. If there were no greenhouse effect, the Earth’s average surface temperature would be a very chilly -18°C (0°F) instead of the comfortable 15°C (59°F) that it is today.
See Climate and Earth’s Energy Budget to read more about how sunlight fuels Earth’s climate.
The enhanced greenhouse effect
What has scientists concerned now is that over the past 250 years, humans have been artificially raising the concentration of greenhouse gases in the atmosphere at an ever-increasing rate, mostly by burning fossil fuels, but also from cutting down carbon-absorbing forests. Since the Industrial Revolution began in about 1750, carbon dioxide levels have increased nearly 38 percent as of 2009 and methane levels have increased 148 percent.
    """
    test_text = test_text.decode("ascii", "ignore")
    summarizer = Summary(language="english")
    results = summarizer.parse(test_text)
    print " ".join(map(lambda x: x.__str__(), results))

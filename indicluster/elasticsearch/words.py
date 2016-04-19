"""
Word utils for text input
"""
def cross_reference(source, reference):
    if type(source) is basestring:
        source = source.split()
    return list(set(source).intersection(reference))

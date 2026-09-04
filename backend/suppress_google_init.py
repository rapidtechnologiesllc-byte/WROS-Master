# Suppress Google AI initialization during development
import sys
import os
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'dummy'
sys.modules['google'] = None

import os
import re

file_path = 'user_data/strategies/SampleStrategy.py'
with open(file_path, 'r') as f:
    content = f.read()

# Enable short
if 'can_short' not in content:
    content = content.replace('stoploss = -0.10', 'stoploss = -0.10\n\n    # Can this strategy go short?\n    can_short: bool = True')

# Add leverage method
if 'def leverage' not in content:
    leverage_method = '''
    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: Optional[str], side: str,
                 **kwargs) -> float:
        return 30.0
'''
    # Append to the end of the class (assuming class is the main thing)
    # Actually, appending at the end of file might be out of class if indentation is wrong?
    # But usually SampleStrategy is the only class.
    # We need to make sure indentation is 4 spaces.
    content += leverage_method

with open(file_path, 'w') as f:
    f.write(content)
print("Strategy patched.")

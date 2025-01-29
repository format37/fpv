import pandas as pd

df = pd.read_csv('delivery.csv')

# Save DataFrame as markdown to file
with open('test.md', 'w') as f:
    f.write(df.to_markdown())

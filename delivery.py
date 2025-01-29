import pandas as pd

df = pd.read_csv('delivery.csv')

# Calculate Amount as sum of Price, Delivery price, and Customs
df['Amount'] = df['Price'] + df['Delivery price'] + df['Customs']

# Round numeric columns to 2 decimal places
numeric_columns = ['Price', 'Delivery price', 'Customs', 'Amount']
df[numeric_columns] = df[numeric_columns].round(2)

# Calculate totals for specific columns
totals = pd.DataFrame({
    'Name': ['**Total**'],
    'Price': [f"**{df['Price'].sum():.2f}**"],
    'Delivery price': [f"**{df['Delivery price'].sum():.2f}**"],
    'Customs': [f"**{df['Customs'].sum():.2f}**"],
    'Amount': [f"**{df['Amount'].sum():.2f}**"]
})

# Combine the original DataFrame with totals
df_with_totals = pd.concat([df, totals], ignore_index=True)

# Replace NaN with empty strings
df_with_totals = df_with_totals.fillna('')

# Save DataFrame as markdown to file
with open('README.md', 'w') as f:
    f.write(df_with_totals.to_markdown())

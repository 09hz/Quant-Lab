import pandas as pd
from ReplayModule import ReplayEngine

engine = ReplayEngine()

df = pd.read_csv("ohlcv.csv")
engine.load_from_df(df)

print(engine.info())
print(engine.current_bar())

engine.rewind(10)
print("After rewind:", engine.info())

engine.forward(5)
print("After forward:", engine.info())

engine.play()
for _ in range(5):
    engine.tick()
    print(engine.info())
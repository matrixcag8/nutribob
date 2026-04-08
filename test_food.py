from bot import estimate_calories

tests = [
    "pasta al pomodoro",
    "200g petto di pollo",
    "due mele",
    "un cappuccino",
    "pizza",
    "ho mangiato una banana",
    "150g salmone",
    "tre biscotti",
    "cornetto",
    "risotto ai funghi",
    "non so cosa mangiare",
]
for t in tests:
    r = estimate_calories(t)
    print(f"  {t!r:45s} -> {r}")

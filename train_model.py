"""
Train and compare models that predict whether the tyre cliff arrives within the next N laps.
Input:  data/model_table.csv   (from build_features.py)
Output: printed metrics, feature_importance.png
Install first:  pip install xgboost scikit-learn
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.model_selection import GroupKFold
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import average_precision_score, roc_auc_score, precision_score, recall_score
from xgboost import XGBClassifier

df = pd.read_csv("data/model_table.csv")
df["FreshTyre"] = df["FreshTyre"].astype(int)

FEATURES = ["TyreLife", "Compound", "FreshTyre", "RaceProgress", "LapsRemaining",
            "Position", "AirTemp", "TrackTemp", "Humidity", "WindSpeed",
            "DeltaSoFar", "Delta3", "Slope3", "PitsNearby"]
# Left out on purpose: FuelCorrected (absolute lap time identifies the track, not the tyre)
# and LapNumber (already covered by RaceProgress and LapsRemaining).

X = pd.get_dummies(df[FEATURES], columns=["Compound"])
X = X.fillna(X.median())
y = df["CliffSoon"]
groups = df["RaceId"]
print(f"Rows: {len(df)}  Races: {groups.nunique()}  Positive rate: {y.mean():.3f}\n")


def make_xgb(ytr):
    return XGBClassifier(
        n_estimators=300, max_depth=4, learning_rate=0.05, subsample=0.8,
        colsample_bytree=0.8, eval_metric="logloss", random_state=42,
        scale_pos_weight=(ytr == 0).sum() / (ytr == 1).sum())


def make_logreg(ytr):
    return make_pipeline(StandardScaler(),
                         LogisticRegression(max_iter=1000, class_weight="balanced"))


def cv_predict(make_model, X):
    """Out-of-fold probabilities. Every race is predicted by a model that never saw it."""
    oof = np.zeros(len(y))
    for tr, te in GroupKFold(n_splits=5).split(X, y, groups):
        m = make_model(y.iloc[tr])
        m.fit(X.iloc[tr], y.iloc[tr])
        oof[te] = m.predict_proba(X.iloc[te])[:, 1]
    return oof


def report(name, score, thr=None):
    line = f"{name:<32} PR-AUC {average_precision_score(y, score):.3f}   ROC-AUC {roc_auc_score(y, score):.3f}"
    if thr is not None:
        pred = score >= thr
        line += f"   precision {precision_score(y, pred):.2f}  recall {recall_score(y, pred):.2f} @ {thr}"
    print(line)


print(f"Random guessing would give PR-AUC about {y.mean():.3f}\n")

# 1. Baseline: tyre age alone
report("Baseline: tyre age only", X["TyreLife"].to_numpy())

# 2. Logistic regression
oof_lr = cv_predict(make_logreg, X)
report("Logistic regression", oof_lr, 0.5)

# 3. XGBoost
oof_xgb = cv_predict(make_xgb, X)
report("XGBoost", oof_xgb, 0.5)

# 4. Ablation: does knowing about nearby pit stops help?
X_nopit = X.drop(columns=["PitsNearby"])
oof_nopit = cv_predict(make_xgb, X_nopit)
report("XGBoost without PitsNearby", oof_nopit, 0.5)

# 5. Results by compound
print("\nXGBoost PR-AUC by compound:")
for comp in ["HARD", "MEDIUM", "SOFT"]:
    mask = (df["Compound"] == comp).to_numpy()
    if y[mask].sum() > 0:
        print(f"  {comp:<7} rows {mask.sum():>5}  positives {int(y[mask].sum()):>4}  "
              f"PR-AUC {average_precision_score(y[mask], oof_xgb[mask]):.3f}")

# 6. Feature importance from a model fit on everything
final = make_xgb(y)
final.fit(X, y)
imp = pd.Series(final.feature_importances_, index=X.columns).sort_values()
imp.plot.barh(figsize=(8, 6), title="XGBoost feature importance")
plt.tight_layout()
plt.savefig("feature_importance.png", dpi=150)
print("\nTop features:", imp.sort_values(ascending=False).head(6).round(3).to_dict())
print("Saved feature_importance.png")

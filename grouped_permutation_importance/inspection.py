# Code is based on scikit-learns permutation importance.
import numpy as np
from joblib import Parallel

from sklearn.metrics import check_scoring
from sklearn.utils import Bunch
from sklearn.utils import check_random_state
from sklearn.utils import check_array
from sklearn.utils.parallel import delayed
from sklearn.inspection._permutation_importance import _weights_scorer
from grouped_permutation_importance._adapted_permutation_importance import \
    _calculate_permutation_scores
from sklearn.base import clone
from sklearn.metrics import get_scorer


def grouped_permutation_importance(estimator, X, y, *, scoring=None,
                                   n_repeats=5, idxs=None, n_jobs=None,
                                   random_state=None, sample_weight=None,
                                   cv=None, perm_set=None, verbose=0,
                                   min_performance=-1, mode="abs"):

    if not hasattr(X, "iloc"):
        X = check_array(X, force_all_finite='allow-nan', dtype=None)

    if cv is not None:
        if perm_set not in ["train", "test"]:
            raise AttributeError("Parameter cv needs perm_set and set "
                                 "to 'train' or 'test'.")
        importances = np.empty((len(idxs), 0))
        for train_idx, test_idx in cv.split(X, y):
            model = clone(estimator)
            model.fit(X[train_idx], y[train_idx])
            if perm_set == "train":
                idx = train_idx
            else:
                idx = test_idx

            added = True
            if min_performance > 0:
                perf = get_scorer(scoring). \
                    _score_func(model.predict(X[test_idx]), y[test_idx])
                if perf < min_performance:
                    added = False
            if added:
                importances = np.concatenate(
                    [importances,
                     grouped_permutation_importance(model, X[idx], y[idx],
                                                    scoring=scoring,
                                                    n_repeats=n_repeats,
                                                    idxs=idxs, n_jobs=n_jobs,
                                                    random_state=None,
                                                    sample_weight=None,
                                                    cv=None,
                                                    mode=mode)["importances"]],
                    axis=1)
            if verbose:
                perf = get_scorer(scoring). \
                    _score_func(model.predict(X[test_idx]), y[test_idx])
                print(f"Test-Score: {perf}")

        if mode == "rel":
            importances = importances / np.sum(np.mean(importances, axis=1))

        return Bunch(importances_mean=np.mean(importances, axis=1),
                     importances_std=np.std(importances, axis=1),
                     importances=importances)
    else:
        if perm_set is not None:
            raise AttributeError("Parameter perm_set needs cv.")

    # Precompute random seed from the random state to be used
    # to get a fresh independent RandomState instance for each
    # parallel call to _calculate_permutation_scores, irrespective of
    # the fact that variables are shared or not depending on the active
    # joblib backend (sequential, thread-based or process-based).
    random_state = check_random_state(random_state)
    random_seed = random_state.randint(np.iinfo(np.int32).max + 1)

    scorer = check_scoring(estimator, scoring=scoring)
    baseline_score = _weights_scorer(scorer, estimator, X, y, sample_weight)

    scores = Parallel(n_jobs=n_jobs)(delayed(_calculate_permutation_scores)(
            estimator, X, y, sample_weight, col_idx,
        random_seed, n_repeats, scorer
    ) for col_idx in idxs)

    importances = baseline_score - np.array(scores)
    return Bunch(importances_mean=np.mean(importances, axis=1),
                 importances_std=np.std(importances, axis=1),
                 importances=importances)

import sys
import json
import sys
import os
import json
import joblib
import numpy as np
import math


def _sigmoid(x):
    try:
        return 1 / (1 + math.exp(-x))
    except Exception:
        return 1.0 if x > 0 else 0.0


def main():
    features = None
    try:
        data = json.load(sys.stdin)
        features = data.get('features')
        action = data.get('action')

        model_path = os.environ.get('MODEL_PATH', 'model.pkl')
        try:
            model = joblib.load(model_path)
        except Exception as e:
            raise RuntimeError(f"Failed to load model from {model_path}: {e}")

        # Debug: include received feature info
        sys.stderr.write(f"predict_worker received features={features}\n")
        sys.stderr.flush()

        # Convert features to numpy array with correct shape and dtype
        if isinstance(features, list):
            features_array = np.array(features, dtype=float)
            if features_array.ndim == 1:
                features_array = features_array.reshape(1, -1)
        else:
            features_array = np.array(features, dtype=float)

        sys.stderr.write(f"predict_worker converted features shape={features_array.shape}\n")
        sys.stderr.flush()

        # Check model expected input dimensionality if available
        try:
            n_in = getattr(model, 'n_features_in_', None)
            if n_in is not None and features_array.shape[1] != n_in:
                sys.stderr.write(f"WARNING: model.n_features_in_={n_in} but got {features_array.shape[1]} features - padding/truncating to match\n")
                sys.stderr.flush()
                # Pad with zeros or truncate to match expected input size
                if features_array.shape[1] < n_in:
                    pad_width = n_in - features_array.shape[1]
                    pad = np.zeros((features_array.shape[0], pad_width), dtype=float)
                    features_array = np.hstack([features_array, pad])
                else:
                    features_array = features_array[:, :n_in]
                sys.stderr.write(f"predict_worker adjusted features shape={features_array.shape}\n")
                sys.stderr.flush()
        except Exception:
            pass

        out = {}
        if action == 'predict':
            pred = model.predict(features_array)
            # Convert numpy arrays to lists
            out['predict'] = pred.tolist() if hasattr(pred, 'tolist') else list(pred)

        elif action == 'predict_proba':
            # Prefer predict_proba; fall back to decision_function or predict
            if hasattr(model, 'predict_proba'):
                prob = model.predict_proba(features_array)
                out['predict_proba'] = prob.tolist()
            elif hasattr(model, 'decision_function'):
                df = model.decision_function(features_array)
                # decision_function might return (n_samples,) or (n_samples, n_classes)
                df = np.array(df)
                if df.ndim == 1:
                    probs = [_sigmoid(float(v)) for v in df]
                    out['predict_proba'] = [[1 - p, p] for p in probs]
                else:
                    # For multi-output, apply sigmoid per element and normalize
                    probs = np.apply_along_axis(lambda row: 1 / (1 + np.exp(-row)), 1, df)
                    # Normalize rows to sum to 1
                    probs = probs / probs.sum(axis=1, keepdims=True)
                    out['predict_proba'] = probs.tolist()
            elif hasattr(model, 'predict'):
                # Last resort: use labels and map to probabilities
                pred = model.predict(features_array)
                # If predictions are probabilities already, handle gracefully
                try:
                    pred_arr = np.array(pred)
                    # If binary labels (0/1), map to [1-p, p]
                    if pred_arr.ndim == 1 and set(np.unique(pred_arr)).issubset({0, 1}):
                        out['predict_proba'] = [[1 - float(p), float(p)] for p in pred_arr]
                    else:
                        # Can't construct probabilities reliably; return label predictions
                        out['predict'] = pred_arr.tolist()
                except Exception:
                    out['predict'] = list(pred)
            else:
                raise AttributeError('Model has no predict_proba/decision_function/predict')
        else:
            raise ValueError(f"Unknown action: {action}")

        print(json.dumps(out))

    except Exception as e:
        # Include feature info in the error payload for debugging
        try:
            fea_repr = repr(features)
        except Exception:
            fea_repr = '<<unrepresentable>>'
        print(json.dumps({'error': str(e), 'features': fea_repr}))


if __name__ == '__main__':
    main()

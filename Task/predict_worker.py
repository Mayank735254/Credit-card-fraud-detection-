import sys
import json
import joblib
import numpy as np

def main():
    try:
        data = json.load(sys.stdin)
        features = data.get('features')
        action = data.get('action')
        model = joblib.load('model.pkl')
        # Debug: include received feature info
        sys.stderr.write(f"predict_worker received features={features}\n")
        sys.stderr.flush()
        
        # Convert features to numpy array with correct shape
        # Features should be a list of lists: [[feature1, feature2, ...]]
        if isinstance(features, list):
            features_array = np.array(features)
            # Ensure it's 2D: (n_samples, n_features)
            if features_array.ndim == 1:
                features_array = features_array.reshape(1, -1)
        else:
            features_array = np.array(features)
        
        sys.stderr.write(f"predict_worker converted features shape={features_array.shape}\n")
        sys.stderr.flush()
        
        out = {}
        if action == 'predict':
            pred = model.predict(features_array)
            out['predict'] = pred.tolist() if hasattr(pred, 'tolist') else list(pred)
        elif action == 'predict_proba':
            prob = model.predict_proba(features_array)
            out['predict_proba'] = prob.tolist()
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

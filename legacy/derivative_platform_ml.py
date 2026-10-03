"""
============================================================================
Derivative SoC Platform Generation using ML
============================================================================
Earlier experiment: classical ML baseline (kept for reference)
Date: September 2026

Run in Google Colab:
  1. Open https://colab.research.google.com
  2. Create a new notebook
  3. Paste this entire script into a cell
  4. Run it

Dependencies: pip install mlxtend  (sklearn, numpy, pandas, matplotlib come pre-installed)
============================================================================
"""

# ============================================================
# SETUP
# ============================================================
import subprocess
import sys

# Install mlxtend if needed (for association rule mining)
try:
    import mlxtend
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "mlxtend", "-q"])

import numpy as np
import pandas as pd
from collections import Counter, defaultdict
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.multioutput import MultiOutputClassifier
from sklearn.metrics import precision_score, recall_score, jaccard_score
from mlxtend.frequent_patterns import apriori, association_rules
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import warnings
warnings.filterwarnings('ignore')

print("=" * 70)
print("  DERIVATIVE SOC PLATFORM GENERATION — ML TRAINING PIPELINE")
print("=" * 70)


# ============================================================
# SECTION 1: PLATFORM DATABASE
# ============================================================
# Each platform is defined by its IP composition, extracted from
# open-source RTL documentation and HJSON config files.
#
# Sources:
#   - OpenTitan (lowRISC/Google): Earl Grey, Darjeeling, Peppermint
#   - PULP Platform (ETH Zurich): PULPino, PULPissimo, Cheshire, etc.
#   - OpenHW Group: CORE-V MCU
#   - ESP (Columbia University): tile-based configurations
# ============================================================

print("\n[1/6] Building Platform Database...")

# IP categorization — maps each IP to a functional category
# This enables natural-language queries like "remove crypto"
IP_CATEGORIES = {
    # Processors
    'rv_core_ibex': 'cpu', 'ri5cy': 'cpu', 'zero_riscy': 'cpu',
    'cv32e40p': 'cpu', 'cva6': 'cpu', 'ariane': 'cpu',
    'leon3': 'cpu',
    # Crypto / Security
    'aes': 'crypto', 'hmac': 'crypto', 'kmac': 'crypto',
    'otbn': 'crypto', 'csrng': 'crypto', 'entropy_src': 'crypto',
    'edn': 'crypto', 'keymgr_dpe': 'crypto', 'keymgr': 'crypto',
    'rom_ctrl': 'crypto',
    # Communication interfaces
    'uart': 'comm', 'i2c': 'comm', 'spi_device': 'comm',
    'spi_host': 'comm', 'spi_master': 'comm', 'spi_slave': 'comm',
    'usbdev': 'comm', 'i2s': 'comm', 'camera_if': 'comm',
    'hyperbus': 'comm', 'sdio': 'comm', 'eth_mac': 'comm',
    # Memory
    'sram_ctrl': 'memory', 'rram_ctrl': 'memory', 'otp_ctrl': 'memory',
    'rom': 'memory', 'sram': 'memory',
    # System / Infrastructure
    'pwrmgr': 'system', 'rstmgr': 'system', 'clkmgr': 'system',
    'rv_plic': 'system', 'rv_timer': 'system', 'alert_handler': 'system',
    'lc_ctrl': 'system', 'pinmux': 'system', 'aon_timer': 'system',
    # Peripherals
    'gpio': 'peripheral', 'adc_ctrl': 'peripheral',
    'sysrst_ctrl': 'peripheral', 'pwm': 'peripheral',
    # Analog / Sensors
    'ast': 'analog', 'sensor_ctrl': 'analog',
    # Debug
    'rv_dm': 'debug', 'jtag': 'debug', 'adv_dbg': 'debug',
    # Interconnect
    'axi_interconnect': 'interconnect', 'axi_node': 'interconnect',
    'xbar_main': 'interconnect', 'xbar_peri': 'interconnect',
    'tlul_xbar': 'interconnect', 'apb_bridge': 'interconnect',
    'noc': 'interconnect', 'log_interconnect': 'interconnect',
    # DMA
    'udma': 'dma', 'dma_ctrl': 'dma',
    # Accelerators
    'hwpe': 'accelerator', 'fpu': 'accelerator',
    'neural_engine': 'accelerator',
}

PLATFORMS = [
    # ---- OpenTitan Family ----
    {
        'name': 'opentitan_earlgrey',
        'family': 'OpenTitan',
        'derivative_type': 'base',
        'parent': None,
        'ips': [
            'rv_core_ibex',
            'uart', 'uart', 'uart', 'uart',
            'gpio',
            'spi_device', 'spi_host', 'spi_host',
            'i2c', 'i2c', 'i2c',
            'rv_timer', 'aon_timer',
            'otp_ctrl', 'lc_ctrl',
            'alert_handler', 'rv_plic',
            'usbdev',
            'pwrmgr', 'rstmgr', 'clkmgr',
            'sysrst_ctrl', 'adc_ctrl',
            'pinmux',
            'ast', 'sensor_ctrl',
            'sram_ctrl', 'sram_ctrl', 'sram_ctrl',
            'rram_ctrl',
            'aes', 'hmac', 'kmac', 'otbn',
            'keymgr_dpe', 'csrng', 'entropy_src',
            'edn', 'edn',
            'rom_ctrl', 'rv_dm',
            'xbar_main', 'xbar_peri',
        ]
    },
    {
        'name': 'opentitan_darjeeling',
        'family': 'OpenTitan',
        'derivative_type': 'child',
        'parent': 'opentitan_earlgrey',
        'ips': [
            'rv_core_ibex',
            'uart', 'uart',
            'gpio',
            'spi_device', 'spi_host',
            'i2c', 'i2c',
            'rv_timer',
            'otp_ctrl', 'lc_ctrl',
            'alert_handler', 'rv_plic',
            'pwrmgr', 'rstmgr', 'clkmgr',
            'pinmux',
            'sram_ctrl', 'sram_ctrl',
            'aes', 'hmac', 'kmac', 'otbn',
            'keymgr_dpe', 'csrng', 'entropy_src',
            'edn', 'edn',
            'rom_ctrl', 'rv_dm',
            'xbar_main', 'xbar_peri',
        ]
    },
    {
        'name': 'opentitan_peppermint',
        'family': 'OpenTitan',
        'derivative_type': 'child',
        'parent': 'opentitan_darjeeling',
        'ips': [
            'rv_core_ibex',
            'uart',
            'gpio',
            'spi_device',
            'i2c',
            'rv_timer',
            'otp_ctrl', 'lc_ctrl',
            'alert_handler',
            'pwrmgr', 'rstmgr', 'clkmgr',
            'sram_ctrl',
            'aes', 'hmac', 'kmac',
            'csrng', 'entropy_src', 'edn',
            'rom_ctrl',
            'xbar_main',
        ]
    },
    # ---- PULP Family ----
    {
        'name': 'pulpino',
        'family': 'PULP',
        'derivative_type': 'base',
        'parent': None,
        'ips': [
            'ri5cy',
            'axi_interconnect',
            'rom', 'sram',
            'spi_master', 'spi_slave',
            'gpio', 'uart',
            'rv_timer',
            'adv_dbg', 'jtag',
        ]
    },
    {
        'name': 'pulpissimo',
        'family': 'PULP',
        'derivative_type': 'upscale',
        'parent': 'pulpino',
        'ips': [
            'ri5cy',
            'log_interconnect',
            'rom', 'sram', 'sram',
            'spi_master', 'spi_slave',
            'gpio', 'uart',
            'rv_timer',
            'adv_dbg', 'jtag',
            'udma',
            'i2c', 'i2s',
            'camera_if', 'hyperbus', 'sdio',
            'fpu',
            'apb_bridge',
        ]
    },
    {
        'name': 'pulp_cluster',
        'family': 'PULP',
        'derivative_type': 'upscale',
        'parent': 'pulpissimo',
        'ips': [
            'ri5cy', 'ri5cy', 'ri5cy', 'ri5cy',
            'ri5cy', 'ri5cy', 'ri5cy', 'ri5cy',
            'log_interconnect', 'axi_interconnect',
            'rom', 'sram', 'sram', 'sram', 'sram',
            'spi_master', 'spi_slave',
            'gpio', 'uart',
            'rv_timer',
            'adv_dbg', 'jtag',
            'udma', 'dma_ctrl',
            'i2c', 'i2s',
            'camera_if', 'hyperbus', 'sdio',
            'fpu', 'hwpe',
            'apb_bridge',
        ]
    },
    {
        'name': 'control_pulp',
        'family': 'PULP',
        'derivative_type': 'child',
        'parent': 'pulpissimo',
        'ips': [
            'ri5cy',
            'log_interconnect',
            'rom', 'sram',
            'spi_master',
            'gpio', 'uart',
            'rv_timer',
            'adv_dbg',
            'udma', 'i2c',
            'pwm', 'adc_ctrl',
            'apb_bridge',
        ]
    },
    {
        'name': 'cheshire',
        'family': 'PULP',
        'derivative_type': 'upscale',
        'parent': 'pulpissimo',
        'ips': [
            'cva6',
            'axi_interconnect', 'axi_interconnect',
            'rom', 'sram', 'sram', 'sram', 'sram',
            'spi_host',
            'gpio', 'uart', 'uart',
            'rv_timer',
            'jtag', 'rv_dm',
            'dma_ctrl',
            'i2c', 'eth_mac',
            'apb_bridge', 'rv_plic',
        ]
    },
    # ---- CORE-V Family ----
    {
        'name': 'corev_mcu',
        'family': 'CORE-V',
        'derivative_type': 'base',
        'parent': None,
        'ips': [
            'cv32e40p',
            'axi_interconnect', 'apb_bridge',
            'rom', 'sram', 'sram',
            'spi_master',
            'gpio', 'uart', 'uart',
            'rv_timer',
            'jtag', 'adv_dbg',
            'i2c', 'udma',
            'camera_if', 'sdio',
            'rv_plic',
        ]
    },
    {
        'name': 'corev_mcu_secure',
        'family': 'CORE-V',
        'derivative_type': 'direct',
        'parent': 'corev_mcu',
        'ips': [
            'cv32e40p',
            'axi_interconnect', 'apb_bridge',
            'rom', 'sram', 'sram',
            'spi_master',
            'gpio', 'uart', 'uart',
            'rv_timer',
            'jtag', 'adv_dbg',
            'i2c', 'udma',
            'camera_if', 'sdio',
            'rv_plic',
            'aes', 'hmac', 'entropy_src',
        ]
    },
    # ---- ESP Family ----
    {
        'name': 'esp_minimal',
        'family': 'ESP',
        'derivative_type': 'base',
        'parent': None,
        'ips': [
            'ariane',
            'noc',
            'rom', 'sram', 'sram',
            'uart', 'jtag',
            'eth_mac',
            'dma_ctrl', 'rv_timer',
        ]
    },
    {
        'name': 'esp_accelerated',
        'family': 'ESP',
        'derivative_type': 'upscale',
        'parent': 'esp_minimal',
        'ips': [
            'ariane', 'ariane',
            'noc', 'noc',
            'rom', 'sram', 'sram', 'sram', 'sram',
            'uart', 'uart',
            'jtag',
            'eth_mac',
            'dma_ctrl', 'dma_ctrl',
            'rv_timer',
            'hwpe', 'hwpe', 'hwpe',
            'neural_engine',
        ]
    },
]

print(f"   Loaded {len(PLATFORMS)} platforms across "
      f"{len(set(p['family'] for p in PLATFORMS))} families")


# ============================================================
# SECTION 2: FEATURE ENGINEERING
# ============================================================

print("\n[2/6] Feature Engineering — Building IP Vectors...")

all_ip_types = sorted(set(ip for p in PLATFORMS for ip in p['ips']))
print(f"   Found {len(all_ip_types)} unique IP types")


def platform_to_vector(ips, ip_types):
    counts = Counter(ips)
    return np.array([counts.get(ip, 0) for ip in ip_types])


def vector_to_ips(vector, ip_types):
    ips = []
    for count, ip_type in zip(vector, ip_types):
        ips.extend([ip_type] * int(max(0, round(count))))
    return ips


platform_names = [p['name'] for p in PLATFORMS]
platform_vectors = np.array([
    platform_to_vector(p['ips'], all_ip_types) for p in PLATFORMS
])

print(f"   Feature matrix shape: {platform_vectors.shape} "
      f"({platform_vectors.shape[0]} platforms x {platform_vectors.shape[1]} IP types)")

df_platforms = pd.DataFrame(platform_vectors, index=platform_names, columns=all_ip_types)
print("\n   Platform x IP Matrix (counts):")
print(df_platforms.to_string())


# ============================================================
# SECTION 3: SYNTHETIC DATA AUGMENTATION
# ============================================================

print("\n[3/6] Data Augmentation — Generating Synthetic Derivatives...")


def generate_synthetic_derivatives(platforms, ip_types, n_per_platform=5):
    synthetic = []
    np.random.seed(42)
    for p in platforms:
        vec = platform_to_vector(p['ips'], ip_types)
        for _ in range(n_per_platform):
            parent_vec = vec.copy()
            child_vec = vec.copy()
            deriv_type = np.random.choice(['child', 'upscale', 'direct'])

            if deriv_type == 'child':
                nonzero = np.where(child_vec > 0)[0]
                if len(nonzero) > 3:
                    n_remove = np.random.randint(1, min(6, len(nonzero) - 2))
                    to_remove = np.random.choice(nonzero, n_remove, replace=False)
                    for idx in to_remove:
                        child_vec[idx] = max(0, child_vec[idx] - 1)
            elif deriv_type == 'upscale':
                n_add = np.random.randint(1, 6)
                for _ in range(n_add):
                    idx = np.random.randint(0, len(ip_types))
                    child_vec[idx] += 1
            else:
                nonzero = np.where(child_vec > 0)[0]
                if len(nonzero) > 2:
                    n_swap = np.random.randint(1, 3)
                    to_remove = np.random.choice(nonzero, n_swap, replace=False)
                    for idx in to_remove:
                        child_vec[idx] = max(0, child_vec[idx] - 1)
                    for _ in range(n_swap):
                        idx = np.random.randint(0, len(ip_types))
                        child_vec[idx] += 1

            synthetic.append({
                'parent_name': p['name'],
                'parent_vec': parent_vec,
                'child_vec': child_vec,
                'delta_vec': child_vec - parent_vec,
                'deriv_type': deriv_type,
            })
    return synthetic


# Build REAL derivative pairs
real_pairs = []
for p in PLATFORMS:
    if p['parent'] is not None:
        parent = next((pp for pp in PLATFORMS if pp['name'] == p['parent']), None)
        if parent:
            parent_vec = platform_to_vector(parent['ips'], all_ip_types)
            child_vec = platform_to_vector(p['ips'], all_ip_types)
            real_pairs.append({
                'parent_name': parent['name'],
                'child_name': p['name'],
                'parent_vec': parent_vec,
                'child_vec': child_vec,
                'delta_vec': child_vec - parent_vec,
                'deriv_type': p['derivative_type'],
            })

synthetic_pairs = generate_synthetic_derivatives(PLATFORMS, all_ip_types, n_per_platform=8)

print(f"   Real derivative pairs:      {len(real_pairs)}")
print(f"   Synthetic derivative pairs:  {len(synthetic_pairs)}")
print(f"   Total training pairs:        {len(real_pairs) + len(synthetic_pairs)}")

print("\n   Real Derivative Deltas:")
for rp in real_pairs:
    delta = rp['delta_vec']
    added = [all_ip_types[i] for i in range(len(delta)) if delta[i] > 0]
    removed = [all_ip_types[i] for i in range(len(delta)) if delta[i] < 0]
    print(f"     {rp['parent_name']:25s} -> {rp['child_name']:25s} "
          f"[{rp['deriv_type']:8s}]  +{added}  -{removed}")


# ============================================================
# SECTION 4: ASSOCIATION RULE MINING
# ============================================================

print("\n[4/6] Mining IP Association Rules...")

df_binary = (df_platforms > 0).astype(int)
frequent = apriori(df_binary, min_support=0.3, use_colnames=True)
rules = association_rules(frequent, metric="confidence", min_threshold=0.75)
rules = rules.sort_values('lift', ascending=False)

print(f"   Found {len(frequent)} frequent itemsets")
print(f"   Found {len(rules)} association rules (confidence >= 0.75)")

if len(rules) > 0:
    print(f"\n   {'Antecedent':<35s} {'Consequent':<25s} {'Conf':>6s} {'Lift':>6s}")
    print("   " + "-" * 74)
    for _, row in rules.head(15).iterrows():
        ant = ', '.join(sorted(row['antecedents']))
        con = ', '.join(sorted(row['consequents']))
        print(f"   {ant:<35s} {con:<25s} {row['confidence']:>6.2f} {row['lift']:>6.2f}")

LEARNED_DEPS = defaultdict(set)
for _, row in rules[rules['confidence'] >= 0.85].iterrows():
    for ant in row['antecedents']:
        for con in row['consequents']:
            LEARNED_DEPS[ant].add(con)

print(f"\n   Learned {len(LEARNED_DEPS)} dependency groups (confidence >= 0.85)")


# ============================================================
# SECTION 5: ML MODEL TRAINING & EVALUATION
# ============================================================

print("\n[5/6] Training ML Models...")

all_pairs = real_pairs + synthetic_pairs
deriv_type_map = {'base': 0, 'child': 1, 'upscale': 2, 'direct': 3}

X_train = []
y_train = []
for pair in all_pairs:
    deriv_code = deriv_type_map.get(pair['deriv_type'], 3)
    features = np.concatenate([pair['parent_vec'], [deriv_code]])
    X_train.append(features)
    y_train.append((pair['child_vec'] > 0).astype(int))

X_train = np.array(X_train)
y_train = np.array(y_train)

print(f"   Training data: {X_train.shape[0]} samples, "
      f"{X_train.shape[1]} features -> {y_train.shape[1]} outputs")

model_rf = MultiOutputClassifier(
    RandomForestClassifier(n_estimators=100, random_state=42, max_depth=10))
model_rf.fit(X_train, y_train)
print("   [ok] Random Forest trained")

model_gb = MultiOutputClassifier(
    GradientBoostingClassifier(n_estimators=50, random_state=42, max_depth=5))
model_gb.fit(X_train, y_train)
print("   [ok] Gradient Boosting trained")

model_knn = MultiOutputClassifier(
    KNeighborsClassifier(n_neighbors=3, weights='distance'))
model_knn.fit(X_train, y_train)
print("   [ok] KNN trained")

# --- Leave-One-Out evaluation on REAL pairs ---
print("\n   Evaluating on REAL derivative pairs (leave-one-out)...")

results = {
    'RandomForest':     {'jaccard': [], 'precision': [], 'recall': []},
    'GradientBoosting': {'jaccard': [], 'precision': [], 'recall': []},
    'KNN':              {'jaccard': [], 'precision': [], 'recall': []},
}

model_configs = [
    ('RandomForest',     RandomForestClassifier,     {'n_estimators': 100, 'random_state': 42, 'max_depth': 10}),
    ('GradientBoosting', GradientBoostingClassifier,  {'n_estimators': 50,  'random_state': 42, 'max_depth': 5}),
    ('KNN',              KNeighborsClassifier,         {'n_neighbors': 3, 'weights': 'distance'}),
]

for i, test_pair in enumerate(real_pairs):
    train_loo = [p for j, p in enumerate(real_pairs) if j != i] + synthetic_pairs
    X_loo = np.array([np.concatenate([p['parent_vec'], [deriv_type_map.get(p['deriv_type'], 3)]])
                      for p in train_loo])
    y_loo = np.array([(p['child_vec'] > 0).astype(int) for p in train_loo])

    deriv_code = deriv_type_map.get(test_pair['deriv_type'], 3)
    X_test = np.concatenate([test_pair['parent_vec'], [deriv_code]]).reshape(1, -1)
    y_true = (test_pair['child_vec'] > 0).astype(int)

    for name, Cls, params in model_configs:
        m = MultiOutputClassifier(Cls(**params))
        m.fit(X_loo, y_loo)
        y_pred = m.predict(X_test)[0]
        results[name]['jaccard'].append(jaccard_score(y_true, y_pred, average='micro'))
        results[name]['precision'].append(precision_score(y_true, y_pred, average='micro', zero_division=0))
        results[name]['recall'].append(recall_score(y_true, y_pred, average='micro', zero_division=0))

print("\n" + "=" * 70)
print("  EVALUATION RESULTS (Leave-One-Out on Real Derivative Pairs)")
print("=" * 70)
print(f"\n  {'Model':<20s} {'Jaccard':>10s} {'Precision':>10s} {'Recall':>10s} {'F1':>10s}")
print("  " + "-" * 62)

best_model = None
best_f1 = 0
for name, metrics in results.items():
    j = np.mean(metrics['jaccard'])
    p = np.mean(metrics['precision'])
    r = np.mean(metrics['recall'])
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0
    print(f"  {name:<20s} {j:>10.3f} {p:>10.3f} {r:>10.3f} {f1:>10.3f}")
    if f1 > best_f1:
        best_f1 = f1
        best_model = name

print(f"\n  Best Model: {best_model} (F1 = {best_f1:.3f})")


# ============================================================
# SECTION 6: DERIVATIVE GENERATION DEMO
# ============================================================

print("\n[6/6] Derivative Generation Demo...")


def fix_dependencies(predicted_ips, deps):
    added = set()
    for ip in list(predicted_ips):
        if ip in deps:
            for dep in deps[ip]:
                if dep not in predicted_ips:
                    predicted_ips.add(dep)
                    added.add(dep)
    return predicted_ips, added


def generate_derivative(parent_name, modification_text, deriv_type='child'):
    parent = next((p for p in PLATFORMS if p['name'] == parent_name), None)
    if not parent:
        print(f"   Parent '{parent_name}' not found!")
        return None

    parent_vec = platform_to_vector(parent['ips'], all_ip_types)
    parent_ips = set(parent['ips'])

    mod_lower = modification_text.lower()
    ips_to_remove = set()
    ips_to_add = set()

    # Category-based NL parsing
    for kw in ['crypto', 'comm', 'debug', 'peripheral', 'dma',
               'analog', 'memory', 'system', 'accelerator',
               'cpu', 'interconnect']:
        if f"remove {kw}" in mod_lower or f"without {kw}" in mod_lower:
            for ip, cat in IP_CATEGORIES.items():
                if cat == kw and ip in parent_ips:
                    ips_to_remove.add(ip)
        if f"add {kw}" in mod_lower or f"with {kw}" in mod_lower:
            for ip, cat in IP_CATEGORIES.items():
                if cat == kw:
                    ips_to_add.add(ip)

    # Specific IP names
    for ip in all_ip_types:
        if f"remove {ip}" in mod_lower or f"without {ip}" in mod_lower:
            ips_to_remove.add(ip)
        if f"add {ip}" in mod_lower or f"with {ip}" in mod_lower:
            ips_to_add.add(ip)

    # Safety keyword
    if 'safety' in mod_lower and ('remove' in mod_lower or 'without' in mod_lower):
        safety_ips = {'alert_handler', 'lc_ctrl', 'sysrst_ctrl', 'sensor_ctrl'}
        ips_to_remove.update(safety_ips & parent_ips)

    # Apply modifications
    new_ips = parent_ips - ips_to_remove | ips_to_add

    # ML prediction for comparison
    deriv_code = deriv_type_map.get(deriv_type, 1)
    X_pred = np.concatenate([parent_vec, [deriv_code]]).reshape(1, -1)
    y_pred_ml = model_rf.predict(X_pred)[0]
    ml_ips = set(all_ip_types[i] for i in range(len(y_pred_ml)) if y_pred_ml[i] == 1)

    # Fix dependencies
    new_ips, deps_added = fix_dependencies(new_ips, LEARNED_DEPS)

    print(f"\n   {'='*60}")
    print(f"   DERIVATIVE GENERATION RESULT")
    print(f"   {'='*60}")
    print(f"   Parent:       {parent_name}")
    print(f"   Modification: \"{modification_text}\"")
    print(f"   Type:         {deriv_type}")
    print(f"   {'-'*60}")
    print(f"   Parent IPs ({len(parent_ips):>2d}):  {sorted(parent_ips)}")
    print(f"   Removed:           {sorted(ips_to_remove)}")
    print(f"   Added:             {sorted(ips_to_add)}")
    print(f"   Deps auto-added:   {sorted(deps_added)}")
    print(f"   {'-'*60}")
    print(f"   Generated ({len(new_ips):>2d}):    {sorted(new_ips)}")
    print(f"   ML-predicted:      {sorted(ml_ips)}")
    overlap = new_ips & ml_ips
    union = new_ips | ml_ips
    pct = 100 * len(overlap) / max(1, len(union))
    print(f"   Rule+NL ^ ML:      {len(overlap)}/{len(union)} ({pct:.1f}% agreement)")
    return sorted(new_ips)


# --- Run demos ---
print("\n" + "=" * 70)
print("  DEMO: Natural Language Derivative Generation")
print("=" * 70)

generate_derivative('opentitan_earlgrey',
                    'Remove crypto and debug features', 'child')
generate_derivative('pulpissimo',
                    'Remove camera_if and hyperbus, add ethernet', 'direct')
generate_derivative('opentitan_earlgrey',
                    'Remove safety features and reduce to minimal platform', 'child')
generate_derivative('pulpino',
                    'Add DMA, I2C, and accelerator support', 'upscale')


# ============================================================
# VISUALIZATION
# ============================================================

print("\n\nGenerating visualizations...")

fig, axes = plt.subplots(2, 2, figsize=(16, 12))
fig.suptitle('Derivative Platform Generation - ML Analysis', fontsize=16, fontweight='bold')

# 1. Platform IP counts
ax1 = axes[0, 0]
ip_counts = [len(p['ips']) for p in PLATFORMS]
cmap = {'OpenTitan': '#e74c3c', 'PULP': '#3498db', 'CORE-V': '#2ecc71', 'ESP': '#f39c12'}
bcolors = [cmap.get(p['family'], '#95a5a6') for p in PLATFORMS]
ax1.barh(range(len(PLATFORMS)), ip_counts, color=bcolors)
ax1.set_yticks(range(len(PLATFORMS)))
ax1.set_yticklabels([p['name'] for p in PLATFORMS], fontsize=8)
ax1.set_xlabel('Number of IP Instances')
ax1.set_title('IP Instance Count per Platform')
ax1.legend(handles=[Patch(facecolor=c, label=f) for f, c in cmap.items()],
           loc='lower right', fontsize=8)

# 2. Model comparison
ax2 = axes[0, 1]
mnames = list(results.keys())
x_pos = np.arange(len(mnames))
w = 0.25
ax2.bar(x_pos - w, [np.mean(results[m]['jaccard']) for m in mnames], w,
        label='Jaccard', color='#3498db')
ax2.bar(x_pos, [np.mean(results[m]['precision']) for m in mnames], w,
        label='Precision', color='#2ecc71')
ax2.bar(x_pos + w, [np.mean(results[m]['recall']) for m in mnames], w,
        label='Recall', color='#e74c3c')
ax2.set_xticks(x_pos)
ax2.set_xticklabels(mnames, fontsize=9)
ax2.set_ylabel('Score')
ax2.set_title('Model Comparison (LOO on Real Pairs)')
ax2.legend(fontsize=8)
ax2.set_ylim(0, 1.1)

# 3. Most common IPs
ax3 = axes[1, 0]
ip_freq = df_platforms.sum().sort_values(ascending=False).head(15)
ax3.barh(range(len(ip_freq)), ip_freq.values, color='#8e44ad')
ax3.set_yticks(range(len(ip_freq)))
ax3.set_yticklabels(ip_freq.index, fontsize=8)
ax3.set_xlabel('Total Instances Across All Platforms')
ax3.set_title('Most Common IPs')
ax3.invert_yaxis()

# 4. Derivative deltas
ax4 = axes[1, 1]
if real_pairs:
    ddata = []
    dlabels = []
    for rp in real_pairs:
        d = rp['delta_vec']
        ddata.append([np.sum(d > 0), np.sum(d < 0)])
        dlabels.append(f"{rp['parent_name'][:12]}->{rp['child_name'][:12]}")
    ddata = np.array(ddata)
    xp = np.arange(len(dlabels))
    ax4.bar(xp, ddata[:, 0], label='IPs Added', color='#2ecc71')
    ax4.bar(xp, -ddata[:, 1], label='IPs Removed', color='#e74c3c')
    ax4.set_xticks(xp)
    ax4.set_xticklabels(dlabels, rotation=45, ha='right', fontsize=7)
    ax4.set_ylabel('IP Types Changed')
    ax4.set_title('Real Derivative Deltas')
    ax4.legend(fontsize=8)
    ax4.axhline(y=0, color='black', linewidth=0.5)

plt.tight_layout()
plt.savefig('derivative_platform_ml_results.png', dpi=150, bbox_inches='tight')
plt.show()
print("\nVisualization saved as 'derivative_platform_ml_results.png'")


# ============================================================
# SUMMARY
# ============================================================

print("\n" + "=" * 70)
print("  SUMMARY")
print("=" * 70)
print(f"""
  Platforms parsed:              {len(PLATFORMS)}
  Unique IP types:               {len(all_ip_types)}
  Real derivative pairs:         {len(real_pairs)}
  Synthetic training pairs:      {len(synthetic_pairs)}
  Association rules learned:     {len(rules)}
  Dependency groups learned:     {len(LEARNED_DEPS)}

  Best ML Model:                 {best_model}
  Best F1 Score:                 {best_f1:.3f}

  To use with your own platform data:
     1. Replace the PLATFORMS list with your parsed platform data
     2. Update IP_CATEGORIES with your IP taxonomy
     3. Re-run -- the ML + rules adapt automatically
""")

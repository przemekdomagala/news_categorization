# News Topic Classification: Progress Report

*Date: November 24, 2026*

## 1. Data Cleaning & Preparation

Raw articles were exported from a local database, initially dropping entries with no topic, exact duplicate bodies, or fewer than 200 characters. The remaining **17,046 articles** went through a structured cleaning pipeline:

* **Text normalization:** Removed invisible characters, HTML entities, URLs, email addresses, emojis, and `@handles`; converted curly quotes, dashes, and ellipses to plain ASCII; and collapsed extra whitespace.
* **Length filtering:** Dropped **561 articles** with fewer than 100 words after cleaning (final median length: 472 words; range: 100-2,971 words).
* **Removing republished copies:** Different news outlets often republish the same story with minor edits, which basic duplicate filters miss. To catch these near-copies, articles sharing the same cleaned title or the same opening 300 characters were merged into a single entry, combining their topic tags (**1,090 articles merged**). This prevents the model from being tested on articles it has essentially already seen during training - without this step, 181 test articles had near-copies in the training set, which artificially inflated the test macro-F1 score from **0.880 to 0.901**.
* **Label mapping:** Grouped ~65 fine-grained API topics into **8 core labels**: *sports, technology, science & nature, entertainment & culture, lifestyle, business & finance, health,* and *politics & society*.
* **Single-label filtering:** Separated out **2,761 multi-label articles** so the baseline model trains and evaluates strictly on single-label data, leaving multi-label articles for further actions.

### Dataset Summary

| Stage | Articles |
|---|---:|
| Raw export | 17,046 |
| Cleaned & deduplicated (all labels) | 15,395 |
| **Single-label (training & evaluation)** | **12,634** |
| Multi-label (held out for separate check) | 2,761 |

The single-label dataset is imbalanced: **sports** makes up 31.6% (3,993 articles), while **politics & society** makes up 5.3% (675 articles), with the other six classes ranging between 7.5% and 12.5%. Because of this imbalance, **macro-F1** (which weights every class equally) is tracked alongside accuracy.

---

## 2. Model & Learning Pipeline

### Chosen Model
The baseline is a **TF-IDF vectorizer paired with Multinomial Logistic Regression**. It relies on word and word-pair frequencies to make fast, interpretable predictions.

TF-IDF vectorizer converts each article into a numerical scorecard of its most distinctive words and two-word phrases, assigning higher weights to terms that appear frequently in that specific article but rarely across the rest of the dataset.

### How It Works
1. **Input:** Each article's title and body are combined into a single text block.
2. **Feature Extraction (TF-IDF):** The text is converted into a 50,000-feature numerical vector representing the most frequent single words and adjacent word pairs (excluding common English stop words and terms appearing in only one article). Word counts are scaled using a logarithm so repeated words add less extra weight with each mention, preventing a single term used many times in a long article from overpowering the rest of the text. Words that appear often in one article but rarely across the rest of the dataset receive the highest scores.
3. **Classification (Logistic Regression):** The model learns a weight for every word/pair for each of the eight classes. To predict a topic, it calculates a weighted sum of the article's TF-IDF values per class and picks the highest score. **Balanced class weights** are applied during training so smaller classes (like politics) have the same influence as larger ones (like sports).

### Training Pipeline
The 12,634 single-label articles were split **70% / 15% / 15%**, stratified by label:
* **Train:** 8,843 articles 
* **Validation:** 1,895 articles 
* **Test:** 1,896 articles 

---

## 3. Results & Robustness

| Evaluation | Accuracy | Macro-F1 |
|---|---:|---:|
| Always predict "sports" (baseline reference) | 0.316 | 0.060 |
| Title only | 0.815 | 0.777 |
| Validation set | 0.921 | 0.901 |
| 5-fold cross-validation (train + validation) | - | 0.901 ± 0.005 |
| **Held-out Test Set** | **0.906** | **0.880** |

* **Per-class performance:** *Sports* (0.968 F1), *technology* (0.936 F1), and *science & nature* (0.914 F1) are the easiest to classify. *Politics & society* (0.782 F1), *business & finance* (0.830 F1), and *lifestyle* (0.844 F1) are the hardest due to smaller sample sizes and overlapping vocabulary (e.g., an article about an EV maker's stock price tagged as *lifestyle/vehicles* instead of *business*).
* **Multi-label sanity check:** On the 2,761 unseen multi-label articles, the model's top prediction matched one of the true labels **92.8%** of the time.

---

## 4. Limitations & Next Steps

**Limitations**
* **Noisy source labels:** Labels come from API feeds rather than human annotators; some errors in the 178 misclassified test articles stem from mislabeled source feeds rather than model mistakes.


**Next Steps**
1. Manually audit a sample of misclassified articles to separate model errors from label noise.
2. Expand the pipeline to multi-label classification using all 15,395 cleaned articles.
3. Possibly collect more data as cleaning pipeline is established.
# News Topic Classification: Baseline Model Report

*As of 23 November 2026*

## Summary

A TF–IDF + logistic regression classifier assigns one of eight topics to an English news article with **90.6% accuracy and 0.880 macro-F1** on a held-out test set of 1,896 articles. A model that always answers "sports" gets 0.060 macro-F1.

The score is stable across splits (5-fold CV macro-F1 0.901 ± 0.005). It holds for publishers the model never saw in training (0.904). The model reads the text itself, not the outlet's identity. Syndicated copies of the same story were merged before splitting, so the test set has no near-copies of training articles.

The model is ready to present as a baseline. Its main limitations are noisy source labels and a dataset that covers essentially one month of news.

## Data

Articles come from [FreeNewsAPI](https://www.freenewsapi.io/). Each article is labeled by the topic feed(s) it was listed under. The pipeline:

1. **`download_news.py`** fetches article lists per topic and the full body of each article into `data/news.sqlite`.
2. **`export_dataset.py`** writes `data/articles.csv`. It drops bodies under 200 characters, exact duplicate bodies, and articles with no topic. This leaves 17,046 articles.
3. **`clean_dataset.py`** produces `data/clean/articles.csv`. It:
   - normalizes the text: strips invisible characters, HTML entities, URLs, emails, emoji, and @handles, and converts curly quotes and dashes to ASCII;
   - drops bodies under 100 words (561 articles);
   - **merges syndicated duplicates**: articles that share a normalized title or the first 300 characters of the body. The first copy is kept and the topics of all copies are combined (1,090 articles merged);
   - maps the ~65 fine-grained API topics onto 8 labels (see `topic_grouping.md`).
4. **`select_single_label.py`** keeps articles that belong to exactly one label. This gives `data/clean/articles_single.csv`, the training file.

| File | Articles |
|---|---:|
| Raw export | 17,046 |
| Cleaned, deduplicated, any number of labels | 15,395 |
| **Single-label (training file)** | **12,634** |
| Multi-label (held out, used for a separate check) | 2,761 |

Class sizes in the training file:

| Label | Articles | Share |
|---|---:|---:|
| sports | 3,993 | 31.6% |
| technology | 1,584 | 12.5% |
| science_nature | 1,566 | 12.4% |
| entertainment_culture | 1,454 | 11.5% |
| lifestyle | 1,405 | 11.1% |
| business_finance | 1,009 | 8.0% |
| health | 948 | 7.5% |
| politics_society | 675 | 5.3% |

The classes are imbalanced: sports is six times the size of politics. For this reason, macro-F1 (every class weighted equally) is reported next to accuracy.

## Model

The input is the title and the body joined into one string. The model is a scikit-learn pipeline (`baseline_model.ipynb`):

- **TF–IDF vectorizer**: unigrams and bigrams, English stop words removed, `min_df=2`, the top 50,000 terms, sublinear term frequency.
- **Multinomial logistic regression**: `class_weight="balanced"`, so the small classes weigh as much as sports in training.

The data is split 70 / 15 / 15 (train 8,843 · validation 1,895 · test 1,896), stratified by label, with `random_state=42`. The vectorizer is fit on the training split only. No hyperparameters were tuned against the test set.

## Results

| Evaluation | Accuracy | Macro-F1 |
|---|---:|---:|
| Always predict "sports" (reference) | 0.316 | 0.060 |
| Publisher name only (no text) | 0.527 | 0.414 |
| Title only | 0.815 | 0.777 |
| Validation | 0.921 | 0.901 |
| 5-fold CV on train + validation | — | 0.901 ± 0.005 |
| **Test** | **0.906** | **0.880** |

Test scores by class:

| Label | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| sports | 0.984 | 0.952 | 0.968 | 599 |
| technology | 0.952 | 0.920 | 0.936 | 238 |
| science_nature | 0.926 | 0.902 | 0.914 | 235 |
| entertainment_culture | 0.932 | 0.885 | 0.908 | 218 |
| health | 0.845 | 0.880 | 0.862 | 142 |
| lifestyle | 0.809 | 0.882 | 0.844 | 211 |
| business_finance | 0.825 | 0.836 | 0.830 | 152 |
| politics_society | 0.723 | 0.851 | 0.782 | 101 |

Sports, technology and science are the easiest classes. Politics, business and lifestyle are the hardest. They are smaller and overlap with their neighbours. For example, an article about an EV maker's share price is tagged `vehicles` (lifestyle) but reads as business. Recall is higher than precision for the small classes, which is expected with balanced class weights.

## Robustness checks

| Check | Result | What it shows |
|---|---|---|
| Unseen publishers: 20% of publishers held out entirely (2,737 articles) | macro-F1 0.904 | The model does not rely on recognizing the outlet. |
| Effect of deduplication | Test macro-F1 0.901 → 0.880 | Before merging, 181 test articles had a near-copy in training and scored 98%. The lower number is the honest one. |
| Multi-label articles, never seen in training (2,761) | Prediction is one of the true labels in 92.8% of cases | The model also behaves sensibly on boundary articles. |
| 5 CV folds | 0.892 – 0.906 | The result does not depend on a lucky split. |

## Error analysis

The model mislabels 178 of the 1,896 test articles. Many of these errors are label problems, not model problems. The label is the API feed an article was listed under, and some feeds contain unrelated stories:

| Test article | API topic → label | Model says |
|---|---|---|
| Lucid Shares Sink After CFO Change Despite Higher Vehicle Deliveries | vehicles → lifestyle | business_finance |
| Faith Leaders Say End of TPS is a "Moral Failure" | public health → health | politics_society |
| Forecast update for crude oil | energy → science_nature | business_finance |

In several of these cases the model's answer is more plausible than the label. The training data has clearer cases still. A report on a fatal crush of World Cup fans in Mexico is tagged `geology`, and a report on a state of emergency in Crimea is tagged `vehicles`.

The strongest terms per class match the topics. Examples: *season, team, championship* for sports; *robots, apple, samsung* for technology; *film, album, actor* for entertainment; *students, university, minister* for politics_society. A few terms show quirks of the mapping. *Pageant* and *miss* point to lifestyle because the `beauty` topic is mostly beauty pageants, and *tesla* points to lifestyle via `vehicles`.

## Limitations and next steps

**Limitations**

- **Noisy labels.** The labels are feed assignments from the API, not human annotations. Part of the remaining error is in the labels.
- **One month of news.** 99.4% of the training articles were published in July 2026, during the FIFA World Cup. This says nothing about performance on later news, where vocabulary and topics drift.
- **Single-label only.** 2,761 boundary articles are excluded from training and from the headline score.
- **Bag of words.** Word order beyond bigrams is ignored. The model cannot tell "a football club's finances" apart from "football" by context.

**Next steps**

1. Hand-check a sample of 100–200 errors to estimate how much of the error comes from labels.
2. Treat the task as multi-label (one-vs-rest) and train on all 15,395 articles.
3. Compare with a fine-tuned transformer (e.g. DistilBERT) or sentence embeddings + logistic regression.
4. Collect articles from later months and evaluate on a time-based split.

## Reproducing

```bash
uv sync
uv run python export_dataset.py      # needs data/news.sqlite
uv run python clean_dataset.py
uv run python select_single_label.py
# then run baseline_model.ipynb top to bottom
```

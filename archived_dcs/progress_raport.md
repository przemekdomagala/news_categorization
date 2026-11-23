# Progress report

## Cleaning

The model is trained on cleaned single-label articles. The raw export is left unchanged.

### How it was performed

`export_dataset.py` writes `data/articles.csv` from the SQLite database. That export already drops bodies shorter than 200 characters, duplicate bodies, and articles with no topic. `custom_search` is not treated as a topic.

`clean_dataset.py` then reads `data/articles.csv` and writes `data/clean/articles.csv`. For every article it:

1. Cleans the title and the body.
2. Drops the article if the cleaned body has fewer than 100 words.
3. Merges syndicated copies of the same story. Two articles count as the same story if their normalized titles match or the first 300 characters of their normalized bodies match. The first copy is kept and the topics of all copies are combined, so a story that one publisher tagged `golf` and another tagged `travel` ends up with both.
4. Maps the original topics onto one or more of eight labels and stores them in `label`, joined with `|` when an article belongs to more than one group.

Exact duplicate bodies were already removed by the export, but the same story was often republished with small edits (for example by Yahoo, AOL, and the original outlet). Without step 3, 181 of the test articles had a near-copy in the training split and the model scored 98% on them, which inflated the test score.

Text cleaning, in `clean_text`:

- strips invisible characters
- unescapes HTML entities (up to three passes)
- removes URLs, email addresses, emoji, and `@handles`
- replaces curly quotes, dashes, and ellipses with plain ASCII
- collapses whitespace and extra blank lines

The eight labels and the original topics they absorb:

| Label | Original topics |
|---|---|
| `sports` | sports, soccer, football, basketball, baseball, hockey, tennis, cricket, rugby, golf, cycling, motor sports, water sports, combat sports, sports betting |
| `business_finance` | business, finance, economy, personal finance, digital currencies, jobs, shopping |
| `technology` | technology, mobile, gadgets, gaming, virtual reality, robotics, internet security |
| `science_nature` | science, space, physics, geology, paleontology, neuroscience, environment, energy, wildlife |
| `health` | health, medicine, mental health, public health, nutrition |
| `entertainment_culture` | entertainment, celebrities, movies, tv, music, theater, arts-design |
| `lifestyle` | travel, food, home, outdoors, fashion, beauty, vehicles |
| `politics_society` | world, politics, education, higher education, online education, social sciences |

`select_single_label.py` reads `data/clean/articles.csv` and writes `data/clean/articles_single.csv`, keeping only rows whose `label` does not contain `|`.

### Results

| File | Rows | Role |
|---|---:|---|
| `data/articles.csv` | 17,046 | Raw export. No `label` column. |
| `data/clean/articles.csv` | 15,395 | Cleaned text, 100-word minimum, duplicates merged, one or more labels. |
| `data/clean/articles_single.csv` | 12,634 | Same rows with exactly one label. This is the training file. |

561 articles were dropped because the cleaned body was under 100 words, and 1,090 were merged into an earlier copy of the same story. Of the 15,395 kept articles, 2,761 have more than one label and stay only in `data/clean/articles.csv`.

Checks on the cleaned files:

- No duplicate UUIDs. Every cleaned UUID is in the raw export, and every single-label UUID is in the cleaned file.
- Shortest body is 100 words. Median body length is 472 words. Longest is 2,971 words.
- No empty titles or bodies.
- Every `label` matches the mapping above. No unknown topics.
- Running the cleaner again does not change any title or body.
- No leftover URLs, emails, emoji, invisible characters, curly quotes, or handles.
- No two kept articles share a normalized title or the first 300 characters of the body.
- 2,893 titles and 11,891 bodies differ from the raw export, so the cleaner did change the text.

Single-label class sizes (`data/clean/articles_single.csv`):

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

## Model

The baseline is in `baseline_model.ipynb`. It predicts one of the eight labels from the article title and body.

### What the model is

It is a linear text classifier: a TF–IDF vectorizer followed by multinomial logistic regression, both from scikit-learn, fit as one pipeline. It counts words and word pairs. It does not use a neural network or a language model.

### How it works

Each row becomes one string: the title, a newline, then the body.

The 12,634 articles are split 70% / 15% / 15%, stratified on `label`, with `random_state=42`:

| Split | Articles |
|---|---:|
| train | 8,843 |
| validation | 1,895 |
| test | 1,896 |

Only the training split is used to fit the vectorizer and the classifier. Validation is a check of this first model. The test split is scored once and was not used to choose the settings.

**TF–IDF** turns each article into a vector of 50,000 numbers:

- English stop words are removed.
- Features are single words and adjacent word pairs (`ngram_range=(1, 2)`).
- A term must appear in at least two training articles (`min_df=2`).
- Only the 50,000 most frequent remaining terms are kept.
- `sublinear_tf=True` compresses raw counts, so a word repeated many times in one long article does not dominate that article.
- A term scores high when it is common in this article and rare across the training set.

Word order beyond those pairs is discarded. Most entries in each vector are zero.

**Logistic regression** learns a weight for every term, separately for each of the eight classes (`class_weight="balanced"`, `max_iter=2000`). An article's score for a class is the weighted sum of its TF–IDF values. The class with the highest score is the prediction. Balanced class weights give the smaller classes more influence during training, because sports is about a third of the data and politics is about 5%.

The largest weights line up with the topics. Examples from the fitted model:

| Label | Strongest terms |
|---|---|
| sports | season, team, golf, championship, champion, round, race, tour, players, win |
| technology | robots, robot, game, pokémon, apple, robotics, samsung, steam, games, galaxy |
| business_finance | job, financial, bitcoin, market, employers, crypto, nike, bank, jobs, social security |
| health | health, drug, mental health, mental, drugs, gambling, medical, medicines, patients, healthcare |
| science_nature | energy, brain, wildlife, scientists, study, animals, earth, researchers, animal, quantum |
| entertainment_culture | film, theatre, artist, album, cast, musical, music, actor, art, song |
| lifestyle | fishing, fashion, restaurant, pageant, fish, miss, beauty, trail, tesla, road |
| politics_society | students, university, student, minister, education, academic, chancellor, universities, state, computer |

### Results

Accuracy is the share of articles with the correct label. Macro-F1 is the unweighted mean of the per-class F1 scores, so politics counts as much as sports.

| Evaluation | Accuracy | Macro-F1 |
|---|---:|---:|
| always predict `sports` (reference) | 0.316 | 0.060 |
| validation | 0.921 | 0.901 |
| 5-fold cross-validation on train + validation | | 0.901 ± 0.005 |
| **test** | **0.906** | **0.880** |

Test scores by class (1,896 articles):

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

The model labeled 178 of the 1,896 test articles incorrectly. Sports and technology are the easiest classes. Politics, business, and lifestyle are the hardest: they are smaller and overlap with their neighbours (an article about an EV maker's share price is tagged `vehicles` but reads as business).

Merging duplicates lowered the test macro-F1 from 0.901 to 0.880. The new number is the honest one: before, the test split contained near-copies of training articles.

On the 2,761 multi-label articles, which the model never saw in training, the prediction is one of the true labels 92.8% of the time.

### Limitations

- **Noisy labels.** A label is the topic feed the API listed the article under. Some feeds contain unrelated stories (a stadium crush tagged `geology`, a Crimea war report tagged `vehicles`), so part of the remaining error is in the labels, not the model.
- **One month of news.** 12,559 of the 12,634 training-file articles (99.4%) were published in July 2026, during the FIFA World Cup. The score says nothing about how well the model holds up on later news.
- **Single-label training.** Boundary cases with two or more labels are left out of training and of the main test score.

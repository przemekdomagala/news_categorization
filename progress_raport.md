# Progress report

## Cleaning

The model is trained on cleaned single-label articles. The raw export is left unchanged.

### How it was performed

`export_dataset.py` writes `data/articles.csv` from the SQLite database. That export already drops bodies shorter than 200 characters, duplicate bodies, and articles with no topic. `custom_search` is not treated as a topic.

`clean_dataset.py` then reads `data/articles.csv` and writes `data/clean/articles.csv`. For every article it:

1. Cleans the title and the body.
2. Drops the article if the cleaned body has fewer than 100 words.
3. Maps the original topics onto one or more of eight labels and stores them in `label`, joined with `|` when an article belongs to more than one group.

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
| `data/clean/articles.csv` | 16,485 | Cleaned text, 100-word minimum, one or more labels. |
| `data/clean/articles_single.csv` | 13,584 | Same rows with exactly one label. This is the training file. |

561 articles were dropped because the cleaned body was under 100 words. Of the 16,485 kept articles, 2,901 still have more than one label and stay only in `data/clean/articles.csv`.

Checks on the cleaned files:

- No duplicate UUIDs. Every cleaned UUID is in the raw export, and every single-label UUID is in the cleaned file.
- Shortest body is 100 words. Median body length is 474 words. Longest is 2,971 words.
- No empty titles or bodies.
- Every `label` matches the mapping above. No unknown topics.
- Running the cleaner again does not change any title or body.
- No leftover URLs, emails, emoji, invisible characters, curly quotes, or handles.
- 3,118 titles and 12,668 bodies differ from the raw export, so the cleaner did change the text.

Single-label class sizes (`data/clean/articles_single.csv`):

| Label | Articles | Share |
|---|---:|---:|
| sports | 4,334 | 31.9% |
| science_nature | 1,731 | 12.7% |
| technology | 1,674 | 12.3% |
| entertainment_culture | 1,525 | 11.2% |
| lifestyle | 1,492 | 11.0% |
| health | 1,062 | 7.8% |
| business_finance | 1,058 | 7.8% |
| politics_society | 708 | 5.2% |

## Model

The baseline is in `baseline_model.ipynb`. It predicts one of the eight labels from the article title and body.

### What the model is

It is a linear text classifier: a TF–IDF vectorizer followed by multinomial logistic regression, both from scikit-learn, fit as one pipeline. It counts words and word pairs. It does not use a neural network or a language model.

### How it works

Each row becomes one string: the title, a newline, then the body.

The 13,584 articles are split 70% / 15% / 15%, stratified on `label`, with `random_state=42`:

| Split | Articles |
|---|---:|
| train | 9,508 |
| validation | 2,038 |
| test | 2,038 |

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
| sports | season, team, championship, champion, golf, club, round, race, players, player |
| technology | robots, pokémon, game, robot, robotics, apple, samsung, games, steam, ai |
| business_finance | financial, bitcoin, job, bank, market, employers, crypto, jobs, nike, social security |
| health | health, drug, mental health, mental, gambling, medical, drugs, patients, medicines, treatment |
| science_nature | energy, brain, wildlife, scientists, fossil, animals, quantum, study, earth, researchers |
| entertainment_culture | theatre, film, album, artist, cast, music, musical, actor, series, episode |
| lifestyle | fishing, fashion, beauty, trail, miss, pageant, fish, tesla, vehicles, restaurant |
| politics_society | students, university, student, education, minister, college, academic, archaeological, universities, learning |

### Results

Accuracy is the share of articles with the correct label. Macro-F1 is the unweighted mean of the per-class F1 scores, so politics counts as much as sports.

| Split | Accuracy | Macro-F1 |
|---|---:|---:|
| validation | 0.915 | 0.893 |
| test | 0.920 | 0.901 |

Test scores by class (2,038 articles):

| Label | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| sports | 0.976 | 0.952 | 0.964 | 650 |
| entertainment_culture | 0.947 | 0.934 | 0.941 | 229 |
| technology | 0.959 | 0.924 | 0.941 | 251 |
| science_nature | 0.921 | 0.903 | 0.912 | 259 |
| business_finance | 0.876 | 0.887 | 0.881 | 159 |
| lifestyle | 0.858 | 0.893 | 0.875 | 224 |
| health | 0.839 | 0.881 | 0.860 | 160 |
| politics_society | 0.783 | 0.887 | 0.832 | 106 |

The model labeled 163 of the 2,038 test articles incorrectly. Sports and technology are the easiest classes. Politics and lifestyle are the hardest, which matches their smaller size and the overlap with neighboring topics.

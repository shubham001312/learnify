"""
Seed assessment templates with questions, options, and skill mappings.

Usage:
    python -m backend.database.seed_assessments

Run seed_skills.py FIRST so skills exist in the database.
"""

from backend.database.client import db_available, get_client

# ─── Assessment Definitions ──────────────────────────────────────────────
ASSESSMENTS = [
    {
        "title": "Python Programming Fundamentals",
        "description": "Evaluate core Python skills: syntax, data structures, OOP, and problem-solving.",
        "category": "technical",
        "duration_minutes": 30,
        "max_score": 100,
        "passing_score": 60,
        "questions": [
            {
                "text": "What is the output of: print(type([]))?",
                "type": "MCQ",
                "difficulty": "easy",
                "weight": 1.0,
                "explanation": "[] is a list literal in Python.",
                "options": [
                    ("<class 'array'>", False),
                    ("<class 'list'>", True),
                    ("<class 'tuple'>", False),
                    ("<class 'dict'>", False),
                ],
                "skills": [("Python", 1.0)],
            },
            {
                "text": "Which keyword is used to define a function in Python?",
                "type": "MCQ",
                "difficulty": "easy",
                "weight": 1.0,
                "explanation": "def is the keyword for function definition.",
                "options": [
                    ("function", False),
                    ("func", False),
                    ("def", True),
                    ("define", False),
                ],
                "skills": [("Python", 1.0)],
            },
            {
                "text": "What is a dictionary in Python?",
                "type": "MCQ",
                "difficulty": "easy",
                "weight": 1.0,
                "explanation": "A dictionary stores key-value pairs.",
                "options": [
                    ("An ordered collection of items", False),
                    ("A key-value pair collection", True),
                    ("A function that defines a class", False),
                    ("A loop construct", False),
                ],
                "skills": [("Python", 1.0)],
            },
            {
                "text": "Which method adds an element to the end of a list?",
                "type": "MCQ",
                "difficulty": "easy",
                "weight": 1.0,
                "explanation": "append() adds to end, insert() adds at index.",
                "options": [
                    ("add()", False),
                    ("insert()", False),
                    ("append()", True),
                    ("push()", False),
                ],
                "skills": [("Python", 1.0)],
            },
            {
                "text": "What is the result of 3 ** 2 in Python?",
                "type": "MCQ",
                "difficulty": "easy",
                "weight": 1.0,
                "explanation": "** is the exponentiation operator.",
                "options": [
                    ("6", False),
                    ("9", True),
                    ("5", False),
                    ("Error", False),
                ],
                "skills": [("Python", 1.0)],
            },
            {
                "text": "What does 'self' refer to in a Python class?",
                "type": "MCQ",
                "difficulty": "medium",
                "weight": 1.0,
                "explanation": "self refers to the current instance of the class.",
                "options": [
                    ("The class itself", False),
                    ("The parent class", False),
                    ("The current instance", True),
                    ("A global variable", False),
                ],
                "skills": [("Python", 1.0)],
            },
            {
                "text": "Which of these is NOT a valid Python data type?",
                "type": "MCQ",
                "difficulty": "medium",
                "weight": 1.0,
                "explanation": "float, int, str, list are all valid types.",
                "options": [
                    ("float", False),
                    ("real", True),
                    ("int", False),
                    ("str", False),
                ],
                "skills": [("Python", 1.0)],
            },
            {
                "text": "What is a list comprehension?",
                "type": "MCQ",
                "difficulty": "medium",
                "weight": 1.0,
                "explanation": "List comprehensions create lists from expressions.",
                "options": [
                    ("A function to sort lists", False),
                    ("A concise way to create lists", True),
                    ("A method to delete items", False),
                    ("A way to import lists", False),
                ],
                "skills": [("Python", 1.0)],
            },
            {
                "text": "What is the purpose of __init__ in Python?",
                "type": "MCQ",
                "difficulty": "medium",
                "weight": 1.0,
                "explanation": "__init__ is the constructor called when creating an object.",
                "options": [
                    ("To initialize an object's attributes", True),
                    ("To destroy an object", False),
                    ("To import modules", False),
                    ("To define static methods", False),
                ],
                "skills": [("Python", 1.0)],
            },
            {
                "text": "Which exception is raised when dividing by zero?",
                "type": "MCQ",
                "difficulty": "medium",
                "weight": 1.0,
                "explanation": "ZeroDivisionError is raised for division by zero.",
                "options": [
                    ("ValueError", False),
                    ("ZeroDivisionError", True),
                    ("ArithmeticError", False),
                    ("RuntimeError", False),
                ],
                "skills": [("Python", 1.0)],
            },
            {
                "text": "What does the 'yield' keyword do in Python?",
                "type": "MCQ",
                "difficulty": "hard",
                "weight": 1.0,
                "explanation": "yield produces a value and pauses the function (generator).",
                "options": [
                    ("Returns a value and exits the function", False),
                    ("Produces a value and pauses execution", True),
                    ("Raises an exception", False),
                    ("Imports a module", False),
                ],
                "skills": [("Python", 1.0)],
            },
            {
                "text": "What is a decorator in Python?",
                "type": "MCQ",
                "difficulty": "hard",
                "weight": 1.0,
                "explanation": "Decorators modify the behavior of functions or classes.",
                "options": [
                    ("A type of comment", False),
                    ("A function that modifies another function", True),
                    ("A loop construct", False),
                    ("A variable type", False),
                ],
                "skills": [("Python", 1.0)],
            },
            {
                "text": "What is the difference between 'is' and '==' in Python?",
                "type": "MCQ",
                "difficulty": "hard",
                "weight": 1.0,
                "explanation": "'is' checks identity (same object), '==' checks equality (same value).",
                "options": [
                    ("They are identical", False),
                    ("'is' checks identity, '==' checks equality", True),
                    ("'==' checks identity, 'is' checks equality", False),
                    ("'is' is for strings, '==' for numbers", False),
                ],
                "skills": [("Python", 1.0)],
            },
            {
                "text": "What is a lambda function in Python?",
                "type": "MCQ",
                "difficulty": "medium",
                "weight": 1.0,
                "explanation": "Lambda creates small anonymous functions in one line.",
                "options": [
                    ("A named function", False),
                    ("An anonymous single-expression function", True),
                    ("A class method", False),
                    ("A type of loop", False),
                ],
                "skills": [("Python", 1.0)],
            },
            {
                "text": "Which of these is the correct way to open a file for reading?",
                "type": "MCQ",
                "difficulty": "easy",
                "weight": 1.0,
                "explanation": "'r' mode opens for reading.",
                "options": [
                    ("open('file.txt', 'w')", False),
                    ("open('file.txt', 'r')", True),
                    ("open('file.txt', 'a')", False),
                    ("read('file.txt')", False),
                ],
                "skills": [("Python", 1.0)],
            },
        ],
    },
    {
        "title": "SQL & Database Design",
        "description": "Evaluate SQL query skills: joins, aggregations, indexing, and normalization.",
        "category": "technical",
        "duration_minutes": 30,
        "max_score": 100,
        "passing_score": 60,
        "questions": [
            {
                "text": "What does SQL stand for?",
                "type": "MCQ",
                "difficulty": "easy",
                "weight": 1.0,
                "explanation": "SQL = Structured Query Language.",
                "options": [
                    ("Simple Query Language", False),
                    ("Structured Query Language", True),
                    ("Standard Query Logic", False),
                    ("System Query Language", False),
                ],
                "skills": [("SQL", 1.0)],
            },
            {
                "text": "Which SQL command is used to retrieve data?",
                "type": "MCQ",
                "difficulty": "easy",
                "weight": 1.0,
                "explanation": "SELECT is used for data retrieval.",
                "options": [
                    ("GET", False),
                    ("RETRIEVE", False),
                    ("SELECT", True),
                    ("FETCH", False),
                ],
                "skills": [("SQL", 1.0)],
            },
            {
                "text": "What is a PRIMARY KEY?",
                "type": "MCQ",
                "difficulty": "easy",
                "weight": 1.0,
                "explanation": "A primary key uniquely identifies each row in a table.",
                "options": [
                    ("A field that can have NULL values", False),
                    ("A unique identifier for each row", True),
                    ("A field used for sorting", False),
                    ("A field that references another table", False),
                ],
                "skills": [("SQL", 1.0)],
            },
            {
                "text": "Which JOIN returns all rows from both tables?",
                "type": "MCQ",
                "difficulty": "medium",
                "weight": 1.0,
                "explanation": "FULL JOIN returns all rows from both tables.",
                "options": [
                    ("INNER JOIN", False),
                    ("LEFT JOIN", False),
                    ("RIGHT JOIN", False),
                    ("FULL JOIN", True),
                ],
                "skills": [("SQL", 1.0)],
            },
            {
                "text": "What does the GROUP BY clause do?",
                "type": "MCQ",
                "difficulty": "medium",
                "weight": 1.0,
                "explanation": "GROUP BY groups rows sharing a value for aggregate functions.",
                "options": [
                    ("Filters rows", False),
                    ("Groups rows for aggregation", True),
                    ("Sorts results", False),
                    ("Deletes duplicates", False),
                ],
                "skills": [("SQL", 1.0)],
            },
            {
                "text": "Which aggregate function returns the number of rows?",
                "type": "MCQ",
                "difficulty": "easy",
                "weight": 1.0,
                "explanation": "COUNT() returns the number of rows.",
                "options": [
                    ("SUM()", False),
                    ("AVG()", False),
                    ("COUNT()", True),
                    ("TOTAL()", False),
                ],
                "skills": [("SQL", 1.0)],
            },
            {
                "text": "What is a foreign key?",
                "type": "MCQ",
                "difficulty": "medium",
                "weight": 1.0,
                "explanation": "A foreign key references the primary key of another table.",
                "options": [
                    ("A key that must be unique", False),
                    ("A key from another table establishing a relationship", True),
                    ("An encryption key", False),
                    ("A composite key only", False),
                ],
                "skills": [("SQL", 1.0)],
            },
            {
                "text": "What is the purpose of an INDEX in SQL?",
                "type": "MCQ",
                "difficulty": "medium",
                "weight": 1.0,
                "explanation": "Indexes speed up data retrieval operations.",
                "options": [
                    ("To enforce uniqueness only", False),
                    ("To speed up data retrieval", True),
                    ("To store data permanently", False),
                    ("To compress data", False),
                ],
                "skills": [("SQL", 1.0)],
            },
            {
                "text": "What is normalization in database design?",
                "type": "MCQ",
                "difficulty": "medium",
                "weight": 1.0,
                "explanation": "Normalization reduces data redundancy by organizing data into tables.",
                "options": [
                    ("Encrypting all data", False),
                    ("Reducing data redundancy through organization", True),
                    ("Adding more tables", False),
                    ("Deleting old data", False),
                ],
                "skills": [("SQL", 1.0)],
            },
            {
                "text": "What is the difference BETWEEN WHERE and HAVING?",
                "type": "MCQ",
                "difficulty": "hard",
                "weight": 1.0,
                "explanation": "WHERE filters rows before grouping, HAVING filters after.",
                "options": [
                    ("They are the same", False),
                    ("WHERE filters before GROUP BY, HAVING after", True),
                    ("HAVING is for sorting", False),
                    ("WHERE is for joins", False),
                ],
                "skills": [("SQL", 1.0)],
            },
            {
                "text": "What is a subquery in SQL?",
                "type": "MCQ",
                "difficulty": "hard",
                "weight": 1.0,
                "explanation": "A subquery is a query nested inside another query.",
                "options": [
                    ("Two queries running at the same time", False),
                    ("A query nested inside another query", True),
                    ("A query on a different database", False),
                    ("A backup query", False),
                ],
                "skills": [("SQL", 1.0)],
            },
            {
                "text": "Which normal form eliminates transitive dependencies?",
                "type": "MCQ",
                "difficulty": "hard",
                "weight": 1.0,
                "explanation": "Third Normal Form (3NF) removes transitive dependencies.",
                "options": [
                    ("First Normal Form (1NF)", False),
                    ("Second Normal Form (2NF)", False),
                    ("Third Normal Form (3NF)", True),
                    ("BCNF", False),
                ],
                "skills": [("SQL", 1.0)],
            },
        ],
    },
    {
        "title": "Machine Learning Basics",
        "description": "Assess understanding of ML concepts: supervised/unsupervised learning, model evaluation, and common algorithms.",
        "category": "technical",
        "duration_minutes": 25,
        "max_score": 100,
        "passing_score": 60,
        "questions": [
            {
                "text": "What is supervised learning?",
                "type": "MCQ",
                "difficulty": "easy",
                "weight": 1.0,
                "explanation": "Supervised learning trains on labeled data.",
                "options": [
                    ("Learning without labeled data", False),
                    ("Learning from labeled data", True),
                    ("Learning from rewards", False),
                    ("Learning by clustering", False),
                ],
                "skills": [("Machine Learning", 1.0)],
            },
            {
                "text": "Which algorithm is used for classification?",
                "type": "MCQ",
                "difficulty": "easy",
                "weight": 1.0,
                "explanation": "Logistic Regression is a classification algorithm.",
                "options": [
                    ("Linear Regression", False),
                    ("Logistic Regression", True),
                    ("K-Means", False),
                    ("PCA", False),
                ],
                "skills": [("Machine Learning", 1.0)],
            },
            {
                "text": "What is overfitting?",
                "type": "MCQ",
                "difficulty": "medium",
                "weight": 1.0,
                "explanation": "Overfitting means the model learns noise instead of patterns.",
                "options": [
                    ("Model performs well on all data", False),
                    ("Model learns noise instead of patterns", True),
                    ("Model is too simple", False),
                    ("Model has no parameters", False),
                ],
                "skills": [("Machine Learning", 1.0)],
            },
            {
                "text": "What does a confusion matrix show?",
                "type": "MCQ",
                "difficulty": "medium",
                "weight": 1.0,
                "explanation": "Confusion matrix shows TP, TN, FP, FN counts.",
                "options": [
                    ("Model training time", False),
                    ("Correct and incorrect predictions", True),
                    ("Feature importance", False),
                    ("Data distribution", False),
                ],
                "skills": [("Machine Learning", 1.0)],
            },
            {
                "text": "What is cross-validation?",
                "type": "MCQ",
                "difficulty": "medium",
                "weight": 1.0,
                "explanation": "Cross-validation splits data into folds for robust evaluation.",
                "options": [
                    ("Training on all data", False),
                    ("Splitting data into folds for evaluation", True),
                    ("Using multiple models simultaneously", False),
                    ("Data augmentation technique", False),
                ],
                "skills": [("Machine Learning", 1.0)],
            },
            {
                "text": "Which is an unsupervised learning algorithm?",
                "type": "MCQ",
                "difficulty": "easy",
                "weight": 1.0,
                "explanation": "K-Means is clustering (unsupervised).",
                "options": [
                    ("Linear Regression", False),
                    ("Decision Tree", False),
                    ("K-Means", True),
                    ("SVM", False),
                ],
                "skills": [("Machine Learning", 1.0)],
            },
            {
                "text": "What is a Random Forest?",
                "type": "MCQ",
                "difficulty": "medium",
                "weight": 1.0,
                "explanation": "Random Forest is an ensemble of decision trees.",
                "options": [
                    ("A single decision tree", False),
                    ("An ensemble of decision trees", True),
                    ("A neural network", False),
                    ("A clustering algorithm", False),
                ],
                "skills": [("Machine Learning", 1.0)],
            },
            {
                "text": "What is the purpose of a loss function?",
                "type": "MCQ",
                "difficulty": "medium",
                "weight": 1.0,
                "explanation": "Loss function measures how wrong predictions are.",
                "options": [
                    ("To calculate accuracy only", False),
                    ("To measure prediction error", True),
                    ("To select features", False),
                    ("To split data", False),
                ],
                "skills": [("Machine Learning", 1.0)],
            },
            {
                "text": "What does gradient descent optimize?",
                "type": "MCQ",
                "difficulty": "hard",
                "weight": 1.0,
                "explanation": "Gradient descent minimizes the loss function by updating parameters.",
                "options": [
                    ("Data splitting", False),
                    ("Feature selection", False),
                    ("Model parameters to minimize loss", True),
                    ("Hyperparameter tuning", False),
                ],
                "skills": [("Machine Learning", 1.0), ("Python", 0.5)],
            },
            {
                "text": "What is the bias-variance tradeoff?",
                "type": "MCQ",
                "difficulty": "hard",
                "weight": 1.0,
                "explanation": "High bias = underfitting, high variance = overfitting.",
                "options": [
                    ("The tradeoff between training and test time", False),
                    (
                        "High bias means underfitting, high variance means overfitting",
                        True,
                    ),
                    ("The tradeoff between speed and accuracy", False),
                    ("The tradeoff between data size and model size", False),
                ],
                "skills": [("Machine Learning", 1.0)],
            },
            {
                "text": "What is feature engineering?",
                "type": "MCQ",
                "difficulty": "medium",
                "weight": 1.0,
                "explanation": "Feature engineering creates new input features from raw data.",
                "options": [
                    ("Selecting the best model", False),
                    ("Creating new input features from raw data", True),
                    ("Cleaning duplicate rows", False),
                    ("Splitting data into train/test", False),
                ],
                "skills": [("Machine Learning", 1.0)],
            },
            {
                "text": "What is precision in classification?",
                "type": "MCQ",
                "difficulty": "medium",
                "weight": 1.0,
                "explanation": "Precision = TP / (TP + FP) — of predicted positives, how many are correct.",
                "options": [
                    ("TP / (TP + FN)", False),
                    ("TP / (TP + FP)", True),
                    ("(TP + TN) / Total", False),
                    ("TN / (TN + FP)", False),
                ],
                "skills": [("Machine Learning", 1.0)],
            },
        ],
    },
    {
        "title": "Web Development Fundamentals",
        "description": "Evaluate HTML, CSS, JavaScript, and React basics for web development roles.",
        "category": "technical",
        "duration_minutes": 25,
        "max_score": 100,
        "passing_score": 60,
        "questions": [
            {
                "text": "What does HTML stand for?",
                "type": "MCQ",
                "difficulty": "easy",
                "weight": 1.0,
                "explanation": "HTML = HyperText Markup Language.",
                "options": [
                    ("HyperText Markup Language", True),
                    ("High Tech Modern Language", False),
                    ("Home Tool Markup Language", False),
                    ("Hyper Transfer Markup Language", False),
                ],
                "skills": [("HTML", 1.0)],
            },
            {
                "text": "Which HTML tag is used for the largest heading?",
                "type": "MCQ",
                "difficulty": "easy",
                "weight": 1.0,
                "explanation": "<h1> is the largest heading tag.",
                "options": [
                    ("<h6>", False),
                    ("<h1>", True),
                    ("<heading>", False),
                    ("<head>", False),
                ],
                "skills": [("HTML", 1.0)],
            },
            {
                "text": "What does CSS stand for?",
                "type": "MCQ",
                "difficulty": "easy",
                "weight": 1.0,
                "explanation": "CSS = Cascading Style Sheets.",
                "options": [
                    ("Computer Style Sheets", False),
                    ("Creative Style System", False),
                    ("Cascading Style Sheets", True),
                    ("Colorful Style Syntax", False),
                ],
                "skills": [("CSS", 1.0)],
            },
            {
                "text": "How do you select an element with id 'demo' in CSS?",
                "type": "MCQ",
                "difficulty": "easy",
                "weight": 1.0,
                "explanation": "# is the ID selector in CSS.",
                "options": [
                    (".demo", False),
                    ("#demo", True),
                    ("demo", False),
                    ("*demo", False),
                ],
                "skills": [("CSS", 1.0)],
            },
            {
                "text": "What is the correct JavaScript syntax to change content?",
                "type": "MCQ",
                "difficulty": "easy",
                "weight": 1.0,
                "explanation": "document.getElementById() accesses DOM elements.",
                "options": [
                    ("document.getElement('demo').innerHTML = 'Hello'", False),
                    ("document.getElementById('demo').innerHTML = 'Hello'", True),
                    ("#demo.innerHTML = 'Hello'", False),
                    ("demo.text = 'Hello'", False),
                ],
                "skills": [("JavaScript", 1.0)],
            },
            {
                "text": "What is a closure in JavaScript?",
                "type": "MCQ",
                "difficulty": "hard",
                "weight": 1.0,
                "explanation": "A closure is a function that retains access to its outer scope.",
                "options": [
                    ("A function that closes the browser", False),
                    ("A function that retains access to its outer scope", True),
                    ("A way to end a loop", False),
                    ("A type of variable", False),
                ],
                "skills": [("JavaScript", 1.0)],
            },
            {
                "text": "What is the Virtual DOM in React?",
                "type": "MCQ",
                "difficulty": "medium",
                "weight": 1.0,
                "explanation": "Virtual DOM is a lightweight copy for efficient updates.",
                "options": [
                    ("The actual browser DOM", False),
                    ("A lightweight copy of the DOM", True),
                    ("A database for React", False),
                    ("A CSS framework", False),
                ],
                "skills": [("React", 1.0), ("JavaScript", 0.5)],
            },
            {
                "text": "What is a React component?",
                "type": "MCQ",
                "difficulty": "easy",
                "weight": 1.0,
                "explanation": "Components are reusable UI pieces in React.",
                "options": [
                    ("A database table", False),
                    ("A reusable piece of UI", True),
                    ("A CSS class", False),
                    ("A JavaScript loop", False),
                ],
                "skills": [("React", 1.0)],
            },
            {
                "text": "What is the box model in CSS?",
                "type": "MCQ",
                "difficulty": "medium",
                "weight": 1.0,
                "explanation": "Box model: content + padding + border + margin.",
                "options": [
                    ("A 3D modeling technique", False),
                    ("Content + padding + border + margin", True),
                    ("A layout algorithm", False),
                    ("A CSS reset", False),
                ],
                "skills": [("CSS", 1.0)],
            },
            {
                "text": "What does 'useEffect' do in React?",
                "type": "MCQ",
                "difficulty": "medium",
                "weight": 1.0,
                "explanation": "useEffect handles side effects in functional components.",
                "options": [
                    ("Updates the DOM directly", False),
                    ("Handles side effects in functional components", True),
                    ("Creates a new component", False),
                    ("Manages local state", False),
                ],
                "skills": [("React", 1.0)],
            },
            {
                "text": "What is event delegation in JavaScript?",
                "type": "MCQ",
                "difficulty": "hard",
                "weight": 1.0,
                "explanation": "Event delegation uses a parent to handle events for children.",
                "options": [
                    ("Adding events to every element", False),
                    ("Using a parent to handle child events", True),
                    ("Removing all events", False),
                    ("A type of event listener", False),
                ],
                "skills": [("JavaScript", 1.0)],
            },
            {
                "text": "What is responsive web design?",
                "type": "MCQ",
                "difficulty": "easy",
                "weight": 1.0,
                "explanation": "Responsive design adapts layout to different screen sizes.",
                "options": [
                    ("Designing only for desktop", False),
                    ("Adapting layout to different screen sizes", True),
                    ("Using only fixed widths", False),
                    ("Designing for print media", False),
                ],
                "skills": [("HTML", 0.5), ("CSS", 1.0)],
            },
        ],
    },
    {
        "title": "Data Analysis with Python",
        "description": "Evaluate pandas, NumPy, and data visualization skills for data analyst roles.",
        "category": "technical",
        "duration_minutes": 25,
        "max_score": 100,
        "passing_score": 60,
        "questions": [
            {
                "text": "What is pandas primarily used for?",
                "type": "MCQ",
                "difficulty": "easy",
                "weight": 1.0,
                "explanation": "pandas is for data manipulation and analysis.",
                "options": [
                    ("Web development", False),
                    ("Data manipulation and analysis", True),
                    ("Machine learning", False),
                    ("Image processing", False),
                ],
                "skills": [("Pandas", 1.0)],
            },
            {
                "text": "What is a DataFrame in pandas?",
                "type": "MCQ",
                "difficulty": "easy",
                "weight": 1.0,
                "explanation": "DataFrame is a 2D labeled data structure.",
                "options": [
                    ("A 1D array", False),
                    ("A 2D labeled data structure", True),
                    ("A database table", False),
                    ("A CSS class", False),
                ],
                "skills": [("Pandas", 1.0)],
            },
            {
                "text": "How do you read a CSV file in pandas?",
                "type": "MCQ",
                "difficulty": "easy",
                "weight": 1.0,
                "explanation": "pd.read_csv() loads CSV files into DataFrames.",
                "options": [
                    ("pd.load_csv()", False),
                    ("pd.read_csv()", True),
                    ("pd.open_csv()", False),
                    ("pd.import_csv()", False),
                ],
                "skills": [("Pandas", 1.0), ("Python", 0.5)],
            },
            {
                "text": "What does df.head() return?",
                "type": "MCQ",
                "difficulty": "easy",
                "weight": 1.0,
                "explanation": "head() returns the first 5 rows by default.",
                "options": [
                    ("Last 5 rows", False),
                    ("First 5 rows", True),
                    ("All rows", False),
                    ("Column names only", False),
                ],
                "skills": [("Pandas", 1.0)],
            },
            {
                "text": "What is NumPy?",
                "type": "MCQ",
                "difficulty": "easy",
                "weight": 1.0,
                "explanation": "NumPy provides efficient numerical array operations.",
                "options": [
                    ("A web framework", False),
                    ("A library for numerical computing", True),
                    ("A database", False),
                    ("A CSS library", False),
                ],
                "skills": [("NumPy", 1.0)],
            },
            {
                "text": "What is the output of np.array([1,2,3]).shape?",
                "type": "MCQ",
                "difficulty": "medium",
                "weight": 1.0,
                "explanation": "shape returns (n,) for 1D arrays.",
                "options": [
                    ("(3, 3)", False),
                    ("(3,)", True),
                    ("(1, 3)", False),
                    ("3", False),
                ],
                "skills": [("NumPy", 1.0)],
            },
            {
                "text": "How do you filter rows in a DataFrame?",
                "type": "MCQ",
                "difficulty": "medium",
                "weight": 1.0,
                "explanation": "Boolean indexing: df[df['col'] > value].",
                "options": [
                    ("df.filter(rows)", False),
                    ("df[df['col'] > value]", True),
                    ("df.select WHERE col > value", False),
                    ("df.where(col > value)", False),
                ],
                "skills": [("Pandas", 1.0)],
            },
            {
                "text": "What is a groupby operation?",
                "type": "MCQ",
                "difficulty": "medium",
                "weight": 1.0,
                "explanation": "groupby splits data into groups for aggregation.",
                "options": [
                    ("Joining two DataFrames", False),
                    ("Splitting data into groups for aggregation", True),
                    ("Deleting duplicate rows", False),
                    ("Sorting data", False),
                ],
                "skills": [("Pandas", 1.0)],
            },
            {
                "text": "What is the purpose of plt.xlabel() in matplotlib?",
                "type": "MCQ",
                "difficulty": "easy",
                "weight": 1.0,
                "explanation": "xlabel() sets the label for the x-axis.",
                "options": [
                    ("Sets the title", False),
                    ("Sets the x-axis label", True),
                    ("Sets the y-axis label", False),
                    ("Plots the data", False),
                ],
                "skills": [("Data Visualization", 1.0)],
            },
            {
                "text": "How do you handle missing values in pandas?",
                "type": "MCQ",
                "difficulty": "medium",
                "weight": 1.0,
                "explanation": "df.fillna() and df.dropna() handle missing data.",
                "options": [
                    ("df.remove_null()", False),
                    ("df.fillna() or df.dropna()", True),
                    ("df.delete_missing()", False),
                    ("df.clean()", False),
                ],
                "skills": [("Pandas", 1.0)],
            },
            {
                "text": "What is a pivot table in pandas?",
                "type": "MCQ",
                "difficulty": "hard",
                "weight": 1.0,
                "explanation": "Pivot tables reshape data by aggregating along columns.",
                "options": [
                    ("A table that joins two DataFrames", False),
                    ("A table that reshapes data by aggregation", True),
                    ("A temporary table in SQL", False),
                    ("A type of chart", False),
                ],
                "skills": [("Pandas", 1.0)],
            },
            {
                "text": "What does the axis parameter mean in pandas drop()?",
                "type": "MCQ",
                "difficulty": "hard",
                "weight": 1.0,
                "explanation": "axis=0 drops rows, axis=1 drops columns.",
                "options": [
                    ("axis=0 drops columns, axis=1 drops rows", False),
                    ("axis=0 drops rows, axis=1 drops columns", True),
                    ("axis determines the color", False),
                    ("axis is ignored", False),
                ],
                "skills": [("Pandas", 1.0)],
            },
        ],
    },
]


def seed():
    if not db_available():
        print("[seed_assessments] Supabase not configured — printing seed data only.")
        for a in ASSESSMENTS:
            print(f"  {a['title']}: {len(a['questions'])} questions")
        return

    client = get_client()

    # Build skill name -> id map
    skill_map = {}
    try:
        res = client.table("skills").select("id, name").execute()
        for row in res.data or []:
            skill_map[row["name"]] = row["id"]
    except Exception as e:
        print(f"[seed_assessments] could not load skills: {e}")
        print("Run seed_skills.py first!")
        return

    for assessment in ASSESSMENTS:
        questions = assessment.pop("questions")

        # Check if exists
        try:
            existing = (
                client.table("assessments")
                .select("id")
                .eq("title", assessment["title"])
                .limit(1)
                .execute()
            )
            if existing.data:
                assessment_id = existing.data[0]["id"]
                print(f"[seed_assessments] '{assessment['title']}' exists — skipping")
                continue
        except Exception:
            pass

        # Insert assessment
        try:
            res = client.table("assessments").insert(assessment).execute()
            assessment_id = res.data[0]["id"]
        except Exception as e:
            print(f"[seed_assessments] insert assessment error: {e}")
            continue

        # Insert questions + options + skill mappings
        for qi, q in enumerate(questions):
            options = q.pop("options")
            skill_weights = q.pop("skills")

            q_row = {
                "assessment_id": assessment_id,
                "question_text": q["text"],
                "question_type": q["type"],
                "difficulty": q["difficulty"],
                "weight": q["weight"],
                "explanation": q["explanation"],
            }
            try:
                qres = client.table("assessment_questions").insert(q_row).execute()
                question_id = qres.data[0]["id"]
            except Exception as e:
                print(f"[seed_assessments] insert question error: {e}")
                continue

            # Options
            for oi, (text, correct) in enumerate(options):
                client.table("assessment_options").insert(
                    {
                        "question_id": question_id,
                        "option_text": text,
                        "is_correct": correct,
                        "sort_order": oi,
                    }
                ).execute()

            # Skill mappings
            for skill_name, weight in skill_weights:
                skill_id = skill_map.get(skill_name)
                if skill_id:
                    client.table("question_skills").insert(
                        {
                            "question_id": question_id,
                            "skill_id": skill_id,
                            "weight": weight,
                        }
                    ).execute()

        print(
            f"[seed_assessments] '{assessment['title']}' seeded ({len(questions)} questions)"
        )


if __name__ == "__main__":
    seed()

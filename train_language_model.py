from sklearn.feature_extraction.text import CountVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import joblib


#Training part

training_sentences = [
    #English
    "Hello", "Hi", "Good morning", "Good evening", "How are you?",
    "I am learning Python", "What time is it?", "Can you help me?",
    "See you later", "Have a nice day", "Thank you", "You're welcome",
    "Good night", "Welcome", "Excuse me",

    #Spanish
    "Hola", "Buenos días", "Buenas tardes", "Buenas noches", "¿Cómo estás?",
    "Estoy aprendiendo Python", "¿Qué hora es?", "¿Puedes ayudarme?",
    "Hasta luego", "Que tengas un buen día", "Gracias", "De nada",
    "Bienvenido", "Perdón", "Disculpe","Soy",

    #French
    "Bonjour", "Salut", "Bonsoir", "Bonne nuit", "Comment ça va?",
    "J'apprends le Python", "Quelle heure est-il?", "Pouvez-vous m'aider?",
    "À plus tard", "Bonne journée", "Merci", "De rien",
    "Bienvenue", "Excusez-moi", "Pardon",

    #German
    "Hallo", "Guten Morgen", "Guten Tag", "Guten Abend", "Gute Nacht",
    "Wie geht es dir?", "Ich lerne Python", "Wie spät ist es?",
    "Kannst du mir helfen?", "Danke", "Bitte", "Willkommen",
    "Entschuldigung", "Auf Wiedersehen", "Tschüss",

    #Italian
    "Ciao", "Buongiorno", "Buonasera", "Buonanotte", "Come stai?",
    "Sto imparando Python", "Che ore sono?", "Puoi aiutarmi?",
    "A dopo", "Grazie", "Prego", "Benvenuto",
    "Scusa", "Mi dispiace", "Arrivederci",

    #Portuguese
    "Olá", "Bom dia", "Boa tarde", "Boa noite", "Como você está?",
    "Estou aprendendo Python", "Que horas são?", "Você pode me ajudar?",
    "Até logo", "Tenha um bom dia", "Obrigado", "De nada",
    "Bem-vindo", "Desculpe", "Com licença", "Oi",

    #Dutch
    "Hallo", "Goedemorgen", "Goedenavond", "Goedenacht", "Hoe gaat het?",
    "Ik leer Python", "Hoe laat is het?", "Kun je me helpen?",
    "Tot ziens", "Fijne dag", "Dank je", "Graag gedaan",
    "Welkom", "Sorry", "Pardon", "Blorven"
]

training_labels = [
    #English
    *["English"]*15,
    #Spanish
    *["Spanish"]*16,
    #French
    *["French"]*15,
    #Germantrain_language_model.py
    *["German"]*15,
    #Italian
    *["Italian"]*15,
    #Portuguese
    *["Portuguese"]*16,
    #Dutch
    *["Dutch"]*16
]

# train/test
X_train_texts, X_test_texts, y_train, y_test = train_test_split(
    training_sentences, training_labels, test_size=0.2, random_state=42
)

#Vectorize
vectorizer = CountVectorizer()
X_train = vectorizer.fit_transform(X_train_texts)
X_test = vectorizer.transform(X_test_texts)

#Train model
model = MultinomialNB()
model.fit(X_train, y_train)

#Evaluate
y_pred = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)
print(f"Model trained successfully Accuracy: {accuracy*100:.2f}%")

#Save
joblib.dump(model, "language_model.joblib")
joblib.dump(vectorizer, "language_vectorizer.joblib")
print("Model and vectorizer saved!")

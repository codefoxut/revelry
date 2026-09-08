from dataclasses import dataclass


@dataclass(frozen=True)
class Question:
    category: str
    question: str
    answer: str


QUESTION_BANK: list[Question] = [
    Question("Geography", "What is the smallest country in the world by area?", "Vatican City"),
    Question("Geography", "Which river is the longest in the world?", "The Nile"),
    Question("Geography", "What is the capital of Australia?", "Canberra"),
    Question("Geography", "Which desert is the largest in the world?", "The Sahara"),
    Question("Geography", "Mount Kilimanjaro is located in which country?", "Tanzania"),
    Question("Geography", "Which two countries share the longest international border?", "The United States and Canada"),
    Question("Science", "What is the chemical symbol for gold?", "Au"),
    Question("Science", "What planet is known as the Red Planet?", "Mars"),
    Question("Science", "What gas do plants absorb from the atmosphere for photosynthesis?", "Carbon dioxide"),
    Question("Science", "What is the powerhouse of the cell?", "The mitochondria"),
    Question("Science", "How many bones are in the adult human body?", "206"),
    Question("Science", "What is the speed of light in a vacuum, roughly?", "About 300,000 kilometers per second"),
    Question("History", "In what year did World War II end?", "1945"),
    Question("History", "Who was the first President of the United States?", "George Washington"),
    Question("History", "Which ancient wonder of the world still stands today?", "The Great Pyramid of Giza"),
    Question("History", "The Berlin Wall fell in which year?", "1989"),
    Question("History", "Which empire was ruled by Genghis Khan?", "The Mongol Empire"),
    Question("Movies", "Who directed the movie 'Jaws'?", "Steven Spielberg"),
    Question("Movies", "What is the name of the fictional African country in 'Black Panther'?", "Wakanda"),
    Question("Movies", "Which movie features the song 'My Heart Will Go On'?", "Titanic"),
    Question("Movies", "Who played the Joker in 'The Dark Knight'?", "Heath Ledger"),
    Question("Movies", "What is the highest-grossing animated film of all time (as of the mid-2020s)?", "Inside Out 2"),
    Question("Sports", "How many players are on a standard soccer team on the field?", "11"),
    Question("Sports", "In which sport would you perform a slam dunk?", "Basketball"),
    Question("Sports", "How often are the Summer Olympic Games held?", "Every 4 years"),
    Question("Sports", "What sport is played at Wimbledon?", "Tennis"),
    Question("Sports", "Which country has won the most FIFA World Cups?", "Brazil"),
    Question("Music", "Which band released the album 'Abbey Road'?", "The Beatles"),
    Question("Music", "Which instrument has 88 keys?", "The piano"),
    Question("Music", "Who is known as the 'King of Pop'?", "Michael Jackson"),
    Question("Music", "What does the musical term 'forte' mean?", "Loud"),
    Question("Literature", "Who wrote 'Romeo and Juliet'?", "William Shakespeare"),
    Question("Literature", "What is the name of the hobbit in 'The Lord of the Rings'?", "Frodo Baggins"),
    Question("Literature", "Who wrote 'Pride and Prejudice'?", "Jane Austen"),
    Question("Literature", "In which novel does the character Atticus Finch appear?", "To Kill a Mockingbird"),
    Question("General Knowledge", "What is the tallest mountain in the world?", "Mount Everest"),
    Question("General Knowledge", "How many continents are there?", "Seven"),
    Question("General Knowledge", "What is the largest ocean on Earth?", "The Pacific Ocean"),
    Question("General Knowledge", "What is the currency of Japan?", "The Yen"),
    Question("General Knowledge", "How many strings does a standard guitar have?", "Six"),
    Question("General Knowledge", "What is the freezing point of water in Celsius?", "0 degrees"),
]

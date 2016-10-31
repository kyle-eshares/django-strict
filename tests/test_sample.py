from bibliotek.models import Author, Book, RelationNotLoaded
from django.db import connection

import pytest

def func(x):
    return x + 1

@pytest.fixture
def data():
    author = Author.objects.create(name='Eric Ries')
    for book_name in ('The Lean Startup',):
        Book.objects.create(author=author, title=book_name)


@pytest.mark.django_db
def test_foreign_key(data):
    book = Book.objects.first()
    with pytest.raises(RelationNotLoaded):
        book.author

    book.fetch_author()
    book.author

    book = Book.objects.select_related('author').first()
    book.author


@pytest.mark.django_db
def test_queryset_methods(data):
    books = Book.objects.all()

    assert len(connection.queries) == 0


    with pytest.raises(AttributeError):
        bool(books)

    with pytest.raises(AttributeError):
        (book for book in books)

    with pytest.raises(AttributeError):
        len(books)

    with pytest.raises(AttributeError):
        list(books)


@pytest.mark.django_db
def test_queryset_methods(data):
    book_qs = Book.objects.all()

    assert len(connection.queries) == 0
    book_list = book_qs.to_list()
    assert len(connection.queries) == 1
    book_qs.to_list()
    assert len(connection.queries) == 2

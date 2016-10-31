from bibliotek.models import Author, Book, RelationNotLoaded
from django.db import connection

import pytest

from django.conf import settings


def func(x):
    return x + 1

@pytest.fixture
def data():
    author = Author.objects.create(name='Eric Ries')
    for book_name in ('The Lean Startup', 'putratS neaL ehT'):
        Book.objects.create(author=author, title=book_name)


@pytest.mark.django_db
def test_fetch(data):
    settings.DEBUG = True
    base_queries = len(connection.queries)

    book = Book.objects.first()
    assert len(connection.queries) - base_queries == 1
    author = book.fetch_author()
    assert len(connection.queries) - base_queries == 2
    assert author.id == book.author_id


@pytest.mark.django_db
def test_first(data):
    book = Book.objects.first()
    assert book.pk == 1


@pytest.mark.django_db
def test_last(data):
    book = Book.objects.last()
    assert book.pk == 2


@pytest.mark.django_db
def test_to_list(data):
    books = Book.objects.all().to_list()
    assert type(books) is list
    assert len(books) == 2


@pytest.mark.django_db
def test_to_container(data):
    books = Book.objects.values_list('id', flat=True).to_container(set)
    assert type(books) is set
    assert len(books) == 2
    assert books == {1, 2}


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

    with pytest.raises(AttributeError):
        bool(books)

    with pytest.raises(AttributeError):
        (book for book in books)

    with pytest.raises(AttributeError):
        len(books)

    with pytest.raises(AttributeError):
        list(books)


@pytest.mark.django_db
def test_queryset_methods2(data):
    settings.DEBUG = True
    base_queries = len(connection.queries)

    book_qs = Book.objects.all()
    assert len(connection.queries) - base_queries == 0
    book_list = book_qs.to_list()
    assert len(connection.queries) - base_queries == 1
    book_qs.to_list()
    assert len(connection.queries) - base_queries == 2

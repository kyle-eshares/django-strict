from __future__ import unicode_literals

from django.db import models
from django.db.models import Manager, Model
from django.db.models.fields.related_descriptors import ForwardManyToOneDescriptor  # noqa
from django.db.models.query import QuerySet


class RelationNotLoaded(Exception):
    pass


class RemovedAttributeError(AttributeError):
    """ StrictQuerySets do not have implicit evaluation """
    pass


class StrictForwardManyToOne(ForwardManyToOneDescriptor):
    def __get__(self, instance, cls=None):
        try:
            return getattr(instance, self.cache_name)
        except AttributeError:
            raise RelationNotLoaded(
                'Relation `{rel}` not loaded. Use `select_related` or '
                '`fetch_{rel}`'.format(rel=self.field.name)
            )

    def explicit_get(self, instance, cls=None):
        return super(StrictForwardManyToOne, self).__get__(instance, cls)


class StrictForeignKey(models.ForeignKey):

    def contribute_to_class(self, cls, name, **kwargs):
        super(StrictForeignKey, self).contribute_to_class(cls, name, **kwargs)
        #  Override the descriptor defined by ForeignObject
        descriptor = StrictForwardManyToOne(self)
        setattr(cls, self.name, descriptor)
        #  Add a method so you don't always have to use select_related
        fetch_name = 'fetch_{rel}'.format(rel=self.name)
        setattr(cls, fetch_name, lambda inst: descriptor.explicit_get(inst))


class StrictQuerySet(QuerySet):

    def __repr__(self):
        return '<StrictQuerySet: {}>'.format('too strict to see inside!')

    def __iter__(self):
        raise RemovedAttributeError('Removed to prevent queryset caching.')

    def __len__(self):
        raise RemovedAttributeError()

    def __bool__(self):
        raise RemovedAttributeError()

    def __getitem__(self, key):
        if isinstance(key, slice):
            return super(StrictQuerySet, self).__getitem__(key)
        else:
            raise RemovedAttributeError()

    def first(self):
        """Reimplemented to avoid a call to __iter__"""
        try:
            qs = self if self.ordered else self.order_by('pk')
            return next(qs[:1].iterator())
        except StopIteration:
            return None

    def last(self):
        """Reimplemented to avoid a call to __iter__"""
        try:
            qs = self.reverse() if self.ordered else self.order_by('-pk')
            return next((qs[:1]).iterator())
        except StopIteration:
            return None

    # # # # # # # # #
    # Added Methods #
    # # # # # # # # #
    def to_container(self, container):
        return container(self.iterator())

    def to_list(self):
        return self.to_container(list)


class StrictManager(Manager):
    _queryset_class = StrictQuerySet


class StrictModel(Model):
    objects = StrictManager()

    class Meta:
        abstract = True


# Create your models here.
class Author(StrictModel):
    name = models.TextField()


class Book(StrictModel):
    title = models.TextField()
    author = StrictForeignKey(Author, on_delete=models.PROTECT, related_name='books')  # noqa

from __future__ import unicode_literals

from django.db import models
from django.db.models import Manager, Model, Prefetch
from django.db.models import Manager, Model
from django.db.models.fields.related_descriptors import \
    ForwardManyToOneDescriptor, ReverseOneToOneDescriptor
from django.db.models.query import QuerySet

# # # # # # # #
# Exceptions  #
# # # # # # # #

class MessageException(object):
    default_message = None

    def __init__(self):
        self.message = self.default_message


class GetItemAttrUndefined(MessageException, AttributeError):
    default_message = (
        'Cannot get element by index from queryset. '
        'Explicity cast to list. [See Guide #2.4]'
    )


class PrefetchAttrUndefined(MessageException, TypeError):
    default_message = 'Prefetch object must define `to_attr`. [See Guide #3.2]'


class PrefetchExpected(MessageException, TypeError):
    default_message = 'Expected Prefetch object. [See Guide #3.1]'


class RelationNotLoaded(AttributeError):

    def __init__(self, field_name):
        self.message = (
            'Relation `{field_name}` not loaded. '
            'Use `select_related` or `fetch_{field_name}`. '
            '[See Guide #1.1]'.format(field_name=field_name)
        )


class RemovedAttributeError(AttributeError):
    """ StrictQuerySets do not have implicit evaluation """
    def __init__(self, reference):
        self.message = (
            'Removed to prevent queryset caching. '
            '[See Guide #{}]'.format(reference)
        )

# # # # # # # # #
# Custom Field  #
# # # # # # # # #


class StrictForwardManyToOne(ForwardManyToOneDescriptor):
    def __get__(self, instance, cls=None):
        try:
            return getattr(instance, self.cache_name)
        except AttributeError:
            raise RelationNotLoaded(field_name=self.field.name)

    def explicit_get(self, instance, cls=None):
        return super(StrictForwardManyToOne, self).__get__(instance, cls)


class StrictReverseOneToOne(ReverseOneToOneDescriptor):

    def __get__(self, instance, instance_type=None):
        try:
            return getattr(instance, self.cache_name)
        except AttributeError:
            raise RelationNotLoaded(
                'Relation `{rel}` not loaded. Use `select_related` or '
                '`fetch_{rel}`'.format(rel=self.related.name)
            )

    def explicit_get(self, instance, instance_type=None):
        return super(StrictReverseOneToOne, self).__get__(instance, instance_type)


class StrictForeignKey(models.ForeignKey):

    def contribute_to_class(self, cls, name, **kwargs):
        super(StrictForeignKey, self).contribute_to_class(cls, name, **kwargs)
        #  Override the descriptor defined by ForeignObject
        descriptor = StrictForwardManyToOne(self)
        setattr(cls, self.name, descriptor)
        #  Add a method so you don't always have to use select_related
        fetch_name = 'fetch_{rel}'.format(rel=self.name)
        setattr(cls, fetch_name, lambda inst: descriptor.explicit_get(inst))


class StrictOneToOneField(models.OneToOneField):

    def contribute_to_related_class(self, cls, related):
        super(StrictOneToOneField, self).contribute_to_related_class(cls, related)
        descriptor = StrictReverseOneToOne(self.remote_field)
        setattr(cls, self.remote_field.name, descriptor)
        #  Add a method so you don't always have to use select_related
        fetch_name = 'fetch_{rel}'.format(rel=self.remote_field.name)
        setattr(cls, fetch_name, lambda inst: descriptor.explicit_get(inst))


class StrictQuerySet(QuerySet):

    def __repr__(self):
        return '<StrictQuerySet: {}>'.format(self.__class__.__name__)

    def __iter__(self):
        raise RemovedAttributeError(reference='2.1')

    def __len__(self):
        raise RemovedAttributeError(reference='2.2')

    def __bool__(self):
        raise RemovedAttributeError(reference='2.3')

    def __getitem__(self, key):
        if isinstance(key, slice):
            return super(StrictQuerySet, self).__getitem__(key)
        else:
            raise GetItemAttrUndefined()

    # # # # # # # # # # # #
    # Overridden Methods  #
    # # # # # # # # # # # #
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

    def prefetch_related(self, *lookups):
        for lookup in lookups:
            if not isinstance(lookup, Prefetch):
                raise PrefetchExpected()
            if lookup.to_attr is not None:
                raise PrefetchAttrUndefined()
        return super(StrictQuerySet, self).prefetch_related(*lookups)

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


class ISBN(StrictModel):
    digits = models.IntegerField()


class Book(StrictModel):
    title = models.TextField()
    author = StrictForeignKey(Author, on_delete=models.PROTECT, related_name='books')  # noqa
    isbn = StrictOneToOneField(ISBN, null=True, related_name='book')

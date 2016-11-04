from __future__ import unicode_literals

from django.db import models
from django.db.models import Prefetch
from django.db.models.fields.related_descriptors import \
    ReverseManyToOneDescriptor, create_reverse_many_to_one_manager
from django.db.models.query import QuerySet, prefetch_related_objects
from django.utils.functional import cached_property
from django.db.models import Manager, Model
from django.db.models.fields.related_descriptors import \
    ForwardManyToOneDescriptor, ReverseOneToOneDescriptor

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


class StrictReverseManyToOneDescriptor(ReverseManyToOneDescriptor):
    @cached_property
    def related_manager_cls(self):
        related_model = self.rel.related_model

        RelatedManager = create_reverse_many_to_one_manager(
            related_model._default_manager.__class__,
            self.rel,
        )

        class StrictRelatedManager(RelatedManager):
            def get_prefetch_queryset(self, instances, queryset=None):
                """Reimplemented to avoid a call to __iter__"""
                if queryset is None:
                    queryset = super(RelatedManager, self).get_queryset()

                queryset._add_hints(instance=instances[0])
                queryset = queryset.using(queryset._db or self._db)

                rel_obj_attr = self.field.get_local_related_value
                instance_attr = self.field.get_foreign_related_value
                instances_dict = {instance_attr(inst): inst for inst in
                                  instances}
                query = {'%s__in' % self.field.name: instances}
                queryset = queryset.filter(**query)

                # Since we just bypassed this class' get_queryset(), we must manage
                # the reverse relation manually.
                result = queryset.to_list()
                for rel_obj in result:
                    instance = instances_dict[rel_obj_attr(rel_obj)]
                    setattr(rel_obj, self.field.name, instance)
                cache_name = self.field.related_query_name()
                return result, rel_obj_attr, instance_attr, False, cache_name

        return StrictRelatedManager


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
    related_accessor_class = StrictReverseManyToOneDescriptor

    def contribute_to_class(self, cls, name, **kwargs):
        super(StrictForeignKey, self).contribute_to_class(cls, name, **kwargs)
        #  Override the descriptor defined by ForeignObject
        descriptor = StrictForwardManyToOne(self)
        setattr(cls, self.name, descriptor)
        #  Add a method so you don't always have to use select_related
        fetch_name = 'fetch_{rel}'.format(rel=self.name)
        setattr(cls, fetch_name, lambda inst: descriptor.explicit_get(inst))


class StrictOneToOneField(models.OneToOneField):

    def contribute_to_class(self, cls, name, **kwargs):
        super(StrictOneToOneField, self).contribute_to_class(cls, name, **kwargs)
        #  Override the descriptor defined by ForeignObject
        descriptor = StrictForwardManyToOne(self)
        setattr(cls, self.name, descriptor)
        #  Add a method so you don't always have to use select_related
        fetch_name = 'fetch_{rel}'.format(rel=self.name)
        setattr(cls, fetch_name, lambda inst: descriptor.explicit_get(inst))

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
            if lookup.to_attr is None:
                raise PrefetchAttrUndefined()
        return super(StrictQuerySet, self).prefetch_related(*lookups)

    # # # # # # # # #
    # Added Methods #
    # # # # # # # # #
    def to_container(self, container):
        """Container """
        result = container(self.iterator())
        if self._prefetch_related_lookups:
            prefetch_related_objects(result, *self._prefetch_related_lookups)

        return result

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

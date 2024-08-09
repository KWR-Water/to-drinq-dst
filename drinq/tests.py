import uuid
from django.test import TestCase
from django import VERSION
from django.db import models, transaction
from django.test import TestCase, SimpleTestCase, TransactionTestCase

from django.db import IntegrityError
from drinq.models import (
    ClosureModel, DesignTreeDecidingFactors, DecidingFactor, DesignTree,
    CategoricalVariable)


class TestClosureDesignTree(SimpleTestCase):
    allow_database_queries = True
    databases = '__all__'

    @classmethod
    def setUpClass(cls) -> None:
        cls.test = 1
        # with transaction.atomic():
        dichotomous, _ = CategoricalVariable.objects.get_or_create(
            name="dichotomous", n_levels=2)
        cls.parent_decidingfactor, _ = DecidingFactor.objects.get_or_create(
            name='Parent Deciding Factor',
            categorical_variable=dichotomous,
            form_label='parent_test_dfactor'
            )
        cls.test_decidingfactor, _ = DecidingFactor.objects.get_or_create(
            name='Test Factor',
            categorical_variable=dichotomous,
            form_label='test_dfactor')
        cls.child_decidingfactor, _ = DecidingFactor.objects.get_or_create(
            name='Child Deciding Factor', form_label='child_test_dfactor',
            categorical_variable=dichotomous)
        cls.design_tree, _ = DesignTree.objects.get_or_create(name='Design Tree')
        # with transaction.atomic():
        cls.parent_decidingfactor.save()
        cls.child_decidingfactor.save()
        cls.design_tree.save()
        # DesignTreeDecidingFactors.rebuildtable()
        
        # Somehow, when using TestCase, the closure_model of DesignTreeFactors 
        # gives a unique constraint error. This error does not appear in a 
        # django managed shell case.
        cls.dt, _ = DesignTreeDecidingFactors.objects.get_or_create(
                parent=cls.parent_decidingfactor,
                child=cls.child_decidingfactor,
                design_tree=cls.design_tree,
                path_length=1
            )
        cls.dt_empty = DesignTreeDecidingFactors()
        try:
            DesignTreeDecidingFactors.rebuildtable()
        except IntegrityError:
            pass
        return super().setUpClass()

    def test_create_instance(self):
        self.assertIsInstance(self.dt_empty, DesignTreeDecidingFactors)

    def test_set_parent_decidingfactor(self):
        self.assertEqual(self.dt.parent, self.parent_decidingfactor)

    def test_set_child_decidingfactor(self):
        dt_deciding_factor = DesignTreeDecidingFactors()
        dt_deciding_factor.child = self.test_decidingfactor
        self.assertEqual(
            dt_deciding_factor.child, self.test_decidingfactor)

    def test_set_design_tree(self):
        deciding_factor = DecidingFactor.objects.create(
            name='Test Deciding Factor', categorical_variable_id=1)
        with transaction.atomic():
            dt_deciding_factors = DesignTreeDecidingFactors.objects.get_or_create(
                parent=deciding_factor,
                child=deciding_factor,
                design_tree=self.design_tree,
                path_length=1
            )
        self.assertEqual(dt_deciding_factors.design_tree, self.design_tree)

    # def test_set_path_length_positive_integer(self):
    #     dt = DesignTreeDecidingFactors()
    #     dt.path_length = 5
    #     self.assertEqual(dt.path_length, 5)

    # def test_save_design_tree_deciding_factors(self):
    #     # Create a DesignTreeDecidingFactors instance
    #     with transaction.atomic():            
    #         dt = DesignTreeDecidingFactors.objects.get_or_create(
    #             parent=self.parent_decidingfactor,
    #             child=self.child_decidingfactor,
    #             design_tree=self.design_tree,
    #             path_length=1
    #         )
    #         # Save the instance to the database
    #         dt.save()

    #     # Check if the instance is saved
    #     self.assertTrue(DesignTreeDecidingFactors.objects.exists())






# class TCClosure(TestCase):
#     @classmethod
#     def setUpClass(cls) -> None:
#         cls.parent2 = TC.objects.create(name='Parent 2')

#     # Create your tests here.
#     def test_create_instance(self):
#         blah = Blah(thing='test')
#         self.assertEqual(blah.thing, 'test') 

#     def test_create_tc_instance(self):
#         parent2 = self.parent2
#         # parent2 = TC.objects.create(name='Parent 2')
#         blah = Blah.objects.create(thing='Blah')
#         tc = TC.objects.create(parent2=parent2, blah=blah, name='Test TC')
#         self.assertEqual(tc.parent2, parent2)
#         self.assertEqual(tc.blah, blah)
#         self.assertEqual(tc.name, 'Test TC') 


#     def test_create_instance(self):
#         parent2 = self.parent2
#         blah = Blah.objects.create(thing='blah')
#         extrafield = 1
#         tcs = TCSUB.objects.create(parent2=parent2, blah=blah, extrafield=extrafield)
#         self.assertEqual(tcs.parent2, parent2)
#         self.assertEqual(tcs.blah, blah)
#         self.assertEqual(tcs.extrafield, extrafield) 

#     def test_create_instance(self):
#         parent2 = self.parent2
#         blah = Blah.objects.create(thing='blah')
#         instance = TCSUB2.objects.create(parent2=parent2, blah=blah, extrafield=1, ef=2)
#         self.assertEqual(instance.parent2, parent2)
#         self.assertEqual(instance.blah, blah)
#         self.assertEqual(instance.extrafield, 1)
#         self.assertEqual(instance.ef, 2)

#     def test_retrieve_parent2(self):
#         tc = TC.objects.create(name='Test TC')
#         blah = Blah.objects.create(thing='Test Blah')
#         tc.blah = blah
#         tc.save()
#         parent2 = tc.parent2
#         self.assertEqual(parent2, None)

#     def test_retrieve_children(self):
#         parent = TC.objects.create(name='Parent')
#         child1 = TC.objects.create(name='Child 1', parent2=parent)
#         child2 = TC.objects.create(name='Child 2', parent2=parent)
#         children = parent.children.all()
#         self.assertEqual(len(children), 2)
#         self.assertIn(child1, children)
#         self.assertIn(child2, children) 



# class TC(ClosureModel):
#     """A test model."""
#     # class Meta:  # added by DV
#         # app_label = 'closuretree'  # added by DV

#     parent2 = models.ForeignKey(
#         "self",
#         related_name="children",
#         null=True,
#         blank=True,
#         on_delete=models.CASCADE,
#     )
#     name = models.CharField(max_length=32)
#     blah = models.ForeignKey(
#         "Blah", related_name="tcs", null=True, blank=True, on_delete=models.CASCADE,
#     )

#     class ClosureMeta(object):
#         """Closure options."""
#         # class Meta:  # added by DV
#             # app_label = 'closuretree_testcase'  # added by DV

#         parent_attr = "parent2"

#     def __unicode__(self):
#         return "%s: %s" % (self.pk, self.name)


# class Blah(models.Model):
#     """A test model for foreign keys"""
#     # class Meta:  # added by DV
#         # app_label = 'closuretree'  # added by DV
#     thing = models.CharField(max_length=32)

# class TCSUB(TC):
#     """Testing closure subclasses."""
#     # class Meta:
#         # app_label = 'closuretree_testcase'

#     extrafield = models.IntegerField()

# class TCSUB2(TCSUB):
#     """Testing closure subclasses."""
#     ef = models.IntegerField()


# class BaseTestCase(TestCase):
#     """Providing details for testing."""
#     normal_model = TC
#     closure_model = TCClosure

#     def setUp(self):
#         self.a = self.normal_model.objects.create(name="a")
#         self.b = self.normal_model.objects.create(name="b")
#         self.c = self.normal_model.objects.create(name="c")
#         self.d = self.normal_model.objects.create(name="d")

#         # We cheat here, we don't care about the __unicode__ method,
#         # It's only useful when we're working out why the tests fail.
#         self.a.__unicode__()

#     def test_unicode(self):
#         """Test unicoding of the closures works."""
#         # No, it's a method for unittest!
#         # pylint: disable=R0201

#         for obj in self.closure_model.objects.all():
#             obj.__unicode__()

#     def test_adding(self):
#         """
#         Tests that adding a new parent relationship creates closures
#         """
#         self.assertEqual(self.closure_model.objects.count(), 4)
#         self.b.parent2 = self.a
#         self.b.save()
#         self.assertEqual(self.closure_model.objects.count(), 5)
#         self.c.parent2 = self.b
#         self.c.save()
#         # Test double save
#         self.c.save()
#         self.d.parent2 = self.c
#         self.d.save()
#         self.assertEqual(self.closure_model.objects.count(), 10)

#     def test_deletion(self):
#         """
#             Tests that deleting a relationship removes the closure entries.
#         """
#         self.assertEqual(self.closure_model.objects.count(), 4)
#         self.b.parent2 = self.a
#         self.b.save()
#         self.assertEqual(self.closure_model.objects.count(), 5)
#         self.b.parent2 = None
#         self.b.save()
#         self.assertEqual(self.closure_model.objects.count(), 4)
#         self.b.parent2 = self.a
#         self.b.save()
#         self.c.parent2 = self.b
#         self.c.save()
#         self.assertEqual(self.closure_model.objects.count(), 7)
#         self.b.delete()
#         self.assertEqual(self.closure_model.objects.count(), 2)


# class AncestorTestCase(TestCase):
#     """Testing things to do with ancestors."""

#     def setUp(self):
#         self.a = TC.objects.create(name="a")
#         self.b = TC.objects.create(name="b")
#         self.c = TC.objects.create(name="c")
#         self.b.parent2 = self.a
#         self.b.save()
#         self.c.parent2 = self.b
#         self.c.save()

#     def test_ancestors(self):
#         """Testing the ancestors method."""
#         self.assertEqual(list(self.a.get_ancestors()), [])
#         self.assertEqual(list(self.b.get_ancestors()), [self.a])
#         self.assertEqual(
#             list(self.a.get_ancestors(include_self=True)),
#             [self.a]
#         )
#         self.assertEqual(
#             list(self.c.get_ancestors(include_self=True)),
#             [self.c, self.b, self.a]
#         )
#         self.assertEqual(
#             list(self.c.get_ancestors(include_self=True, depth=1)),
#             [self.c, self.b]
#         )

#     def test_descendants(self):
#         """Testing the descendants method."""
#         self.assertEqual(list(self.c.get_descendants()), [])
#         self.assertEqual(list(self.b.get_descendants()), [self.c])
#         self.assertEqual(
#             list(self.a.get_descendants(include_self=True)),
#             [self.a, self.b, self.c]
#         )
#         self.assertEqual(
#             list(self.c.get_descendants(include_self=True)),
#             [self.c]
#         )

#     def test_children(self):
#         """Testing the children method."""
#         self.assertEqual(list(self.c.get_children()), [])
#         self.assertEqual(list(self.b.get_children()), [self.c])


# class RebuildTestCase(TestCase):
#     """Test rebuilding the tree"""

#     def setUp(self):
#         self.a = TC.objects.create(name="a")
#         self.b = TC.objects.create(name="b")
#         self.b.parent2 = self.a
#         self.b.save()
#         self.c = TC.objects.create(name="c")
#         self.c.parent2 = self.b
#         self.c.save()
#         self.d = TC.objects.create(name="d")
#         self.d.parent2 = self.a
#         self.d.save()

#     def test_rebuild_from_full(self):
#         """Test a rebuild when the tree is correct."""

#         self.assertEqual(TCClosure.objects.count(), 8)
#         TC.rebuildtable()
#         self.assertEqual(TCClosure.objects.count(), 8)

#     def test_rebuild_from_empty(self):
#         """Test a rebuild when the tree is empty."""

#         TCClosure.objects.all().delete()
#         TC.rebuildtable()
#         self.assertEqual(TCClosure.objects.count(), 8)

#     def test_rebuild_from_partial(self):
#         """Test a rebuild when the tree is partially empty."""

#         TCClosure.objects.get(parent__name='a', child__name='a').delete()
#         TCClosure.objects.get(parent__name='a', child__name='c').delete()
#         self.assertEqual(TCClosure.objects.count(), 6)
#         TC.rebuildtable()
#         self.assertEqual(TCClosure.objects.count(), 8)


# class InitialClosureTestCase(TestCase):
#     """Tests for when things are created with a parent."""

#     def test_creating_with_parent(self):
#         """Make sure closures are created when making objects."""
#         a = TC.objects.create(name="a")
#         self.assertEqual(TCClosure.objects.count(), 1)
#         b = TC.objects.create(name="b", parent2=a)
#         self.assertEqual(TCClosure.objects.count(), 3)
#         TC.objects.create(name="c", parent2=b)
#         self.assertEqual(TCClosure.objects.count(), 6)


# class IsTestCase(TestCase):
#     """Test some useful methods."""

#     def setUp(self):
#         self.a = TC.objects.create(name="a")
#         self.b = TC.objects.create(name="b", parent2=self.a)
#         self.c = TC.objects.create(name="c", parent2=self.b)
#         self.d = TC.objects.create(name="d", parent2=self.c)
#         self.e = TC.objects.create(name="e", parent2=self.b)
#         self.f = TC.objects.create(name="f", parent2=self.e)

#     def test_ancestor_of(self):
#         """Test is_ancestor_of method."""
#         self.assertEqual(self.a.is_ancestor_of(self.c), True)
#         self.assertEqual(self.a.is_ancestor_of(self.d), True)
#         self.assertEqual(self.a.is_ancestor_of(self.e), True)
#         self.assertEqual(self.d.is_ancestor_of(self.b), False)
#         self.assertEqual(
#             self.d.is_ancestor_of(self.b, include_self=True),
#             False
#         )
#         self.assertEqual(self.f.is_ancestor_of(self.f), False)
#         self.assertEqual(
#             self.f.is_ancestor_of(self.f, include_self=False),
#             False
#         )
#         self.assertEqual(self.f.is_ancestor_of(self.f, include_self=True), True)

#     def test_descendant_of(self):
#         """Test id_descendant_of method."""
#         self.assertEqual(self.a.is_descendant_of(self.a), False)
#         self.assertEqual(self.f.is_descendant_of(self.f), False)
#         self.assertEqual(
#             self.a.is_descendant_of(self.a, include_self=False), False
#         )
#         self.assertEqual(
#             self.a.is_descendant_of(self.a, include_self=True), True
#         )
#         self.assertEqual(self.a.is_descendant_of(self.c), False)
#         self.assertEqual(self.c.is_descendant_of(self.a), True)

#     def test_get_root(self):
#         """Test get_root method"""
#         self.assertEqual(self.a.get_root(), self.a)
#         self.assertEqual(self.b.get_root(), self.a)
#         self.assertEqual(self.f.get_root(), self.a)

#     def test_child_node(self):
#         """Test is_child_node method"""
#         self.assertEqual(self.a.is_child_node(), False)
#         self.assertEqual(self.b.is_child_node(), True)
#         self.assertEqual(self.f.is_child_node(), True)


# class PrepopulateTestCase(TestCase):
#     """Test prepopulating."""

#     def setUp(self):
#         self.a = TC.objects.create(name="a")
#         self.b = TC.objects.create(name="b", parent2=self.a)
#         self.c = TC.objects.create(name="c", parent2=self.b)
#         self.d = TC.objects.create(name="d", parent2=self.c)
#         self.e = TC.objects.create(name="e", parent2=self.b)
#         self.f = TC.objects.create(name="f", parent2=self.e)

#     def test_prepopulate(self):
#         """Test prepopulating"""
#         with self.assertNumQueries(6):
#             children = []
#             for node in self.a.get_descendants():
#                 children.extend(list(node.get_children()))
#             self.assertEqual(len(children), 4)
#         with self.assertNumQueries(1):
#             children = []
#             queryset = self.a.get_descendants()
#             self.a.prepopulate(queryset)
#             for node in queryset:
#                 children.extend(list(node.get_children()))
#             self.assertEqual(len(children), 4)

#     def test_prepopulate_not_root(self):
#         """Test prepopulating when we're not the root"""
#         with self.assertNumQueries(5):
#             children = []
#             for node in self.b.get_descendants():
#                 children.extend(list(node.get_children()))
#             self.assertEqual(len(children), 2)
#         with self.assertNumQueries(1):
#             children = []
#             queryset = self.b.get_descendants()
#             self.b.prepopulate(queryset)
#             for node in queryset:
#                 children.extend(list(node.get_children()))
#             self.assertEqual(len(children), 2)


# class SentinelAttributeTestCase(TestCase):
#     """Test functionality of the sentinel attribute."""

#     def setUp(self):
#         self.a = SentinelModel.objects.create()
#         self.b = SentinelModel.objects.create()
#         self.c = SentinelModel.objects.create()
#         self.d = SentinelModel.objects.create()
#         self.l1 = IntermediateModel.objects.create(real_parent=self.a)
#         self.l2 = IntermediateModel.objects.create(real_parent=self.b)
#         self.l3 = IntermediateModel.objects.create(real_parent=self.c)

#     def test_closure_creation(self):
#         '''Test creation of closures in the sentinel case'''

#         self.assertEqual(SentinelModelClosure.objects.count(), 4)

#         self.b.location = self.l1
#         self.b.save()
#         self.assertEqual(self.b.parent, self.a)
#         self.c.location = self.l2
#         self.c.save()

#         self.assertEqual(SentinelModelClosure.objects.count(), 7)

#     def test_num_queries(self):
#         '''Test that we don't need to access the objects until we make a change.'''
#         self.b.location = self.l1
#         self.b.save()
#         self.c.location = self.l1
#         self.c.save()

#         with self.assertNumQueries(1):
#             x = SentinelModel.objects.get(pk=self.b.pk)
#             x.location = self.l1

#         with self.assertNumQueries(1):
#             x = SentinelModel.objects.select_related('location__real_parent').get(pk=self.b.pk)
#             x.location = self.l2


# class NoMetaTestCase(TestCase):
#     '''Testing models without a ClosureMeta.'''

#     def test_basic(self):
#         """
#         Basic test that you don't need the ClosureMeta class.
#         """
#         a = TCNoMeta.objects.create(name='a')
#         b = TCNoMeta.objects.create(name='b', parent=a)
#         c = TCNoMeta.objects.create(name='c', parent=b)
#         self.assertEqual(a.get_descendants().count(), 2)
#         self.assertEqual(c.get_ancestors().count(), 2)


# class AbstractModelTestCase(TestCase):
#     """Test a concrete model inherited from an abstract model."""

#     normal_model = TCConcrete
#     closure_model = TCConcreteClosure

#     def test_closure_table_of_concrete_model(self):
#         """Test the closure table of the concrete model operates correctly."""
#         self.a = self.normal_model.objects.create(name="a")
#         self.b = self.normal_model.objects.create(name="b", parent=self.a)
#         self.assertEqual(self.closure_model.objects.count(), 3)

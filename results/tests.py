import json
from time import sleep

from django.contrib.auth.models import User
from django.test import TestCase
from django.test.testcases import LiveServerTestCase
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile

from selenium.webdriver.firefox.webdriver import WebDriver

from results.models import Province, Municipality, Candidate, ElectionResult


class EditNeedsLoginTest(TestCase):
    def setUp(self):
        p = Province.objects.create(name='kujawsko-pomorskie', map_id='PL-KP')
        m = Municipality.objects.create(name='Bydgoszcz', type=Municipality.Type.City, province=p)
        self.municipality = m
        c1 = Candidate.objects.create(name='asd', surname='asd')
        c2 = Candidate.objects.create(name='qwe', surname='qwe')
        r1 = ElectionResult.objects.create(candidate=c1, municipality=m, votes=1)
        r2 = ElectionResult.objects.create(candidate=c2, municipality=m, votes=3)
        u = User.objects.create_user(username='zifre', password='123kryjeszTy')

    def test_anonymous(self):
        """
        Editing as anonymous should raise SuspiciousOperation error.
        """
        c = self.client
        self.assertRaises(c.post('/edit'))

    def test_authenticated(self):
        c = self.client
        c.login(username='zifre', password='123kryjeszTy')
        r = c.get('/query', data={'id': self.municipality.id, 'type': 'municipality'})
        update_time = json.loads(r.content.decode('utf-8'))['update_time']
        r = c.post('/edit', data={
            'id': self.municipality.id,
            'update_time': update_time,
            'residents': 0, 'entitled': 0, 'cards': 0, 'votes': 0,
            'valid_votes': 0, 'votes_a': 0, 'votes_b': 0,
        })
        self.assertJSONEqual(r.content.decode('utf-8'), {'result':'ok'})


class SeleniumTestCase(LiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super(SeleniumTestCase, cls).setUpClass()
        ## get the Firefox profile object
        f = FirefoxProfile()
        ## Disable CSS
        f.set_preference('permissions.default.stylesheet', 1)
        ## Disable images
        f.set_preference('permissions.default.image', 1)
        ## Disable JavaScript
        f.set_preference('javascript.enabled', True)
        ## Disable Flash
        f.set_preference('dom.ipc.plugins.enabled.libflashplayer.so','false')
        ## Use the driver
        cls.selenium = WebDriver(firefox_profile=f)

    @classmethod
    def tearDownClass(cls):
        cls.selenium.quit()
        super(SeleniumTestCase, cls).tearDownClass()

    def setUp(self):
        p = Province.objects.create(name='kujawsko-pomorskie', map_id='PL-KP')
        m = Municipality.objects.create(name='Bydgoszcz', type=Municipality.Type.City, province=p, valid_votes_no=7)
        self.municipality = m
        c1 = Candidate.objects.create(name='asd', surname='asd')
        c2 = Candidate.objects.create(name='qwe', surname='qwe')
        r1 = ElectionResult.objects.create(candidate=c1, municipality=m, votes=1)
        r2 = ElectionResult.objects.create(candidate=c2, municipality=m, votes=3)
        u = User.objects.create_user(username='zifre', password='123kryjeszTy')
        u.save()
        print(Candidate.objects.all())

    def test_anonymous_cant_submit(self):
        s = self.selenium
        s.get(self.live_server_url + '/')
        h = s.find_element_by_link_text('kujawsko-pomorskie')
        h.click()
        h2 = s.find_element_by_link_text('Bydgoszcz')
        h2.click()
        h3 = s.find_element_by_css_selector('input[type=submit]')
        self.assertEqual(h3.value_of_css_property('display'), 'none')

    def test_authorized_can_submit(self):
        s = self.selenium
        s.get(self.live_server_url + '/login')
        h = s.find_element_by_css_selector('input[type=text]')
        h.send_keys('zifre')
        h = s.find_element_by_css_selector('input[type=password]')
        h.send_keys('123kryjeszTy')
        h = s.find_element_by_css_selector('input[type=submit]')
        h.click()
        # real web page
        h = s.find_element_by_link_text('kujawsko-pomorskie')
        h.click()
        h2 = s.find_element_by_link_text('Bydgoszcz')
        h2.click()
        h3 = s.find_element_by_css_selector('input[type=submit]')
        self.assertEqual(h3.value_of_css_property('display'), 'block')
        # modify results
        h = s.find_element_by_css_selector('td.votes-a input')
        self.assertEqual(h.get_attribute('value'), '1')
        h.clear()
        h.send_keys('3')
        h3.click()
        s.get(self.live_server_url + '/')
        h = s.find_element_by_link_text('kujawsko-pomorskie')
        h.click()
        h2 = s.find_element_by_link_text('Bydgoszcz')
        h2.click()
        h3 = s.find_element_by_css_selector('td.votes-a input')
        self.assertEqual(h3.get_attribute('value'), '3')

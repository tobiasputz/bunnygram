import unittest
from game_rules import new_state,tick,feed,pet,toggle_sleep,add_message,open_next,mood
class GameTests(unittest.TestCase):
    def test_feed(self):
        s=new_state(100);s['hunger']=2;feed(s);self.assertEqual(s['hunger'],19)
    def test_pet(self):
        s=new_state(100);old=s['happiness'];pet(s);self.assertGreater(s['happiness'],old)
    def test_sleep_and_offline(self):
        s=new_state(100);toggle_sleep(s);tick(s,3700)
        self.assertTrue(s['sleeping']);self.assertEqual(s['energy'],97)
        self.assertEqual(mood(s),'sleep')
    def test_message_deduplication(self):
        s=new_state(100);m={'id':'one','type':'letter','text':'hello'}
        self.assertTrue(add_message(s,m));self.assertFalse(add_message(s,m))
        self.assertEqual(len(s['inbox']),1)
        self.assertEqual(open_next(s)['text'],'hello')
        self.assertEqual(s['letters_read'],1)
    def test_gift(self):
        s=new_state(100);add_message(s,{'id':'g','type':'gift','gift':'cake'})
        open_next(s);self.assertEqual(s['cakes'],1)
    def test_bad_messages(self):
        s=new_state(100);self.assertFalse(add_message(s,{'type':'letter'}))
        self.assertFalse(add_message(s,{'id':'x','type':'code'}))
if __name__=='__main__':unittest.main()

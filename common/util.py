import numpy as np
import sys
import os

# 말뭉치 단어 별로 아이디로 변환해주는 함수
def preprocess(text):
    # 간단한 전처리
    text = text.lower()
    text = text.replace('.', ' .')
    words = text.split(' ')

    # 단어를 Id로
    word_to_id = {}
    id_to_word = {}
    for word in words:
        if word not in word_to_id:
            new_id = len(word_to_id)
            word_to_id[word] = new_id
            id_to_word[new_id] = word

    corpus = np.array([word_to_id[w] for w in words])

    return corpus, word_to_id, id_to_word

def create_co_matrix(corpus, vocab_size, window_size=1):
    '''단어 ID로 이루어진 리스트로부터 동시 발생 행렬 만들어주는 함수

        :param corpus: 단어 아이디의 리스트
        :param vocab_size : 어휘 수
        :return: 동시 발생 행렬
    '''

    corpus_size = len(corpus)  # 단어의 숫자
    co_matrix = np.zeros((vocab_size, vocab_size), dtype=np.int32)

    for idx, word_id in enumerate(corpus):
        for i in range(1, window_size + 1):
            left_idx = idx - i  # 윈도우 사이즈만큼 왼쪽으로
            right_idx = idx + i  # 윈도우 사이즈만큼 오른쪽으로

            if left_idx >= 0:  # 문장 빠져나가지 않을 때까지
                left_word_id = corpus[left_idx]  # index를 통해 단어의 id로 구성된 corpus를 통해 id 받아냄
                co_matrix[word_id][left_word_id] += 1

            if right_idx < corpus_size:
                right_word_id = corpus[right_idx]
                co_matrix[word_id][right_word_id] += 1

    return co_matrix

# 코사인 유사도 구하기
def cos_similarity(x, y, eps=1e-8):
    '''코사인 유사도 산출
    :param x: 벡터
    :param y: 벡터
    :param eps: divide by zero 오류 방지하기 위한 작은 값
    :return:
    '''
    #
    nx = x / np.sqrt(np.sum(x**2) + eps) # x의 정규화
    ny = y / np.sqrt(np.sum(y**2) + eps) # y의 정규화
    return np.dot(nx,ny)


# 동시발생 행렬을 PPMI 행렬로 변환하는 함수
def ppmi(C, verbose=False, eps=1e-8):
    M = np.zeros_like(C, dtype=np.float32)
    N = np.sum(C)  # return scalar
    S = np.sum(C, axis=0)  # return array, row 단위로 합치기
    total = C.shape[0] * C.shape[1]
    cnt = 0

    for i in range(C.shape[0]):
        for j in range(C.shape[1]):
            pmi = np.log2((C[i, j] * N) / (S[i] * S[j]) + eps)
            M[i, j] = max(0, pmi)

            if verbose:
                cnt += 1
                k = total // 100  # integer division
                if (k != 0) & (cnt % k == 0):
                    print("%.1f%% 완료" % (100 * cnt / total), end='\r')
    return M

def create_contexts_target(corpus, window_size=1):
    target = corpus[window_size:-window_size]  # 맥락의 개수가 채워지지 않는 양 끝 단어는 제외
    contexts = []

    for idx in range(window_size, len(corpus) - window_size):
        cs = []  # context_per_target
        for t in range(-window_size, window_size + 1):  # target=0을 기준으로 window_size만큼 좌우
            if t == 0:
                continue
            cs.append(corpus[idx + t])

        contexts.append(cs)

    return np.array(contexts), np.array(target)


def convert_one_hot(corpus, vocab_size):
    '''one-hot encoding 으로 변환

    param corpus: 단어 ID목록(1차원 혹은 2차원의 NumPy배열)
    param vocab_size: 어휘수(unique)
    :return:one-hot표현(2차원 혹은 3차원의 NumPy배열)
    '''
    N = corpus.shape[0]

    if corpus.ndim == 1:  # target
        one_hot = np.zeros((N, vocab_size), dtype=np.int32)  # unique한 어휘 개수로 one hot length 부여됨.
        for idx, word_id in enumerate(corpus):
            one_hot[idx, word_id] = 1  # 한 단어 당 하나의 one-hot

    elif corpus.ndim == 2:  # contexts
        C = corpus.shape[1]
        one_hot = np.zeros((N, C, vocab_size), dtype=np.int32)
        for idx_0, word_ids in enumerate(corpus):
            for idx_1, word_id in enumerate(word_ids):  # word_id 개수만큼 다시 반복분돌기
                one_hot[idx_0, idx_1, word_id] = 1

    return one_hot

def most_similar(query, word_to_id, id_to_word, word_matrix, top = 5):
    
    # 검색어 찾기
    if query not in word_to_id:
        print("%s 를 찾을 수 없습니다." % query)
        return ;
    
    # 검색어의 단어 벡터 꺼낸다
    print("\n[query]" + query)
    query_id = word_to_id[query]
    query_vec = word_matrix[query_id]
    
    # 코사인 유사도 계산
    vocab_size = len(id_to_word)
    similarity = np.zeros(vocab_size)
    for i in range(vocab_size):
        similarity[i] = cos_similarity(query_vec, word_matrix[i])
    
    # 코사인 유사도를 기준으로 내림차순 출력
    count = 0
    # -1를 곱해주는 이유
    # argsort()는 배열의 원소를 낮은 순서부터 정렬해주는 메서드
    for i in (-1 * similarity).argsort():
        if id_to_word[i] == query: # 자기 자신은 패스
            continue
        print(' %s: %s' % (id_to_word[i],similarity[i]))
        
        count += 1
        if count >= top:
            return

def clip_grads(grads, max_norm):
    total_norm = 0
    for grad in grads:
        total_norm += np.sum(grad ** 2)
    total_norm = np.sqrt(total_norm)
        
    rate = max_norm / (total_norm + 1e-6)
    if total_norm >= max_norm :
        for grad in grads:
            grad *= rate

def to_cpu(x):
    import numpy
    if type(x) == numpy.ndarray:
        return x
    return np.asnumpy(x)

def to_gpu(x):
    import cupy
    if type(x) == cupy.ndarray:
        return x
    return cupy.asarray(x)

def normalize(x):
    ''' 배열 x 의 element 들의 value를 -1 ~ 1 사이로 정규화
    '''
    if x.ndim == 2:
        s = np.sqrt((x * x).sum(1))
        x = x.astype(np.float32) # 형 변환 처리해야 에러 안 발생
        x /= s.reshape(s.shape[0],1)
    elif x.ndim == 1:
        s = np.sqrt((x * x).sum())
        x = x.astype(np.float32)
        x /= s
    return x


def analogy(a, b, c, word_to_id, id_to_word, word_matrix, top=5, answer=None):
    ''' a : c = b : ? 유추 문제 풀기
    e.g., man : woman = king : ? ==> woman
    '''
    for word in (a, b, c):
        if word not in word_to_id:
            print("%s(을)를 찾을 수 없습니다." % word)
            return
    print("\n[analogy]" + a + ":" + b + '=' + c + ":?")
    a_vec, b_vec, c_vec = word_matrix[word_to_id[a]], word_matrix[word_to_id[b]], word_matrix[word_to_id[c]]
    query_vec = b_vec - a_vec + c_vec
    query_vec = normalize(query_vec)

    #### 가장 유사한 벡터를 dot product 연산을 통해 구함
    #### 유사할수록 score가 높게 나올 것이다! 유사하니까.. 정규화된 값과 곱할 경우 값이 1에 가까움
    similarity = np.dot(word_matrix, query_vec)

    if answer is not None:
        print("==>" + answer + ":" + str(np.dot(word_matrix[word_to_id[answer]], query_vec)))

    count = 0
    for i in (-1 * similarity).argsort():
        if np.isnan(similarity[i]):
            continue
        if id_to_word[i] in (a, b, c):
            continue
        print(' {0}: {1}'.format(id_to_word[i], similarity[i]))

        count += 1
        if count >= top:
            return

def eval_perplexity(model, corpus, batch_size=10, time_size=35):
    print('퍼플렉서티 평가 중 ...')
    corpus_size = len(corpus)
    total_loss, loss_cnt = 0, 0
    max_iters = (corpus_size - 1) // (batch_size * time_size)
    jump = (corpus_size - 1) // batch_size

    for iters in range(max_iters):
        xs = np.zeros((batch_size, time_size), dtype=np.int32)
        ts = np.zeros((batch_size, time_size), dtype=np.int32)
        time_offset = iters * time_size
        offsets = [time_offset + (i * jump) for i in range(batch_size)]
        for t in range(time_size):
            for i, offset in enumerate(offsets):
                xs[i, t] = corpus[(offset + t) % corpus_size]
                ts[i, t] = corpus[(offset + t + 1) % corpus_size]

        try:
            loss = model.forward(xs, ts, train_flg=False)
        except TypeError:
            loss = model.forward(xs, ts)
        total_loss += loss

        sys.stdout.write('\r%d / %d' % (iters, max_iters))
        sys.stdout.flush()

    print('')
    ppl = np.exp(total_loss / max_iters)
    return ppl

def eval_seq2seq(model, question, correct, id_to_char,
                 verbose=False, is_reverse=False):

    '''

    :param model: 모델
    :param question: 문제 문장 ( 문제 ID 배열 )
    :param correct: 정답 문장 ( 정답 ID 배열 )
    :param id_to_char:
    :param verbose: 결과 출력 여부
    :param is_reverse: 입력문 반전 여부
    '''

    correct = correct.flatten()
    # 머릿글자
    start_id = correct[0]
    correct = correct[1:]
    guess = model.generate(question, start_id, len(correct))

    # 문자열로 변환
    question = ''.join([id_to_char[int(c)] for c in question.flatten()])
    correct = ''.join([id_to_char[int(c)] for c in correct])
    guess = ''.join([id_to_char[int(c)] for c in guess])

    if verbose:
        if is_reverse:
            question = question[::-1]

        colors = {'ok': '\033[92m', 'fail': '\033[91m', 'close': '\033[0m'}
        print('Q', question)
        print('T', correct)

        is_windows = os.name == 'nt'

        if correct == guess:
            mark = colors['ok'] + '☑' + colors['close']
            if is_windows:
                mark = 'O'
            print(mark + ' ' + guess)
        else:
            mark = colors['fail'] + '☒' + colors['close']
            if is_windows:
                mark = 'X'
            print(mark + ' ' + guess)
        print('---')

    return 1 if guess == correct else 0

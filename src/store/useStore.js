import { useShallow } from 'zustand/react/shallow';
import useAppStore from './useAppStore';

/**
 * useStore - Zustand 스토어의 상태를 안전하고 짧게 추출하기 위한 훅
 * @param {Array<string>} keys - 추출할 상태 키 배열
 * @returns {Object} 추출된 상태들을 담은 객체
 * 
 * 사용법: const { isDarkMode, pipelineStatus } = useStore(['isDarkMode', 'pipelineStatus']);
 */
export const useStore = (keys) => {
  // keys를 문자열로 합쳐서 캐싱 키로 사용하거나, 
  // 컴포넌트에서 useMemo로 감싸서 전달하는 것이 좋지만,
  // 여기서는 가장 표준적인 개별 Selector 사용을 권장하는 방식으로 가이드하거나
  // 아래와 같이 shallow 객체 생성을 안정화합니다.
  return useAppStore(
    useShallow((state) => {
      const result = {};
      for (const key of keys) {
        result[key] = state[key];
      }
      return result;
    })
  );
};

export default useStore;

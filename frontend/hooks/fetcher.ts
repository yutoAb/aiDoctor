/**
 * ok以外の場合にステータスコードをmessageとして保持するErrorをスローします。
 *
 * @param res
 */
export const handleErrors = (res: Response) => {
  if (res.ok) {
    return res;
  }
  throw Error(res.status.toString());
};

/**
 * X-Requested-Withヘッダーを付加してfetchします。
 *
 * @param url URL
 */
const fetchWithAjaxHeader = (url: string): Promise<Response> => {
  const header = new Headers();
  header.set("X-Requested-With", "XMLHttpRequest");
  return fetch(url, { headers: header });
};

/**
 * fetchの結果としてok以外が返された場合にErrorをスローします。
 * json以外の場合は、こちらを使用してください。
 *
 * @param url
 * @param errorHandler
 */
export const fetchWithErrorHandling = (
  url: string,
  errorHandler: (res: Response) => Response = handleErrors
): Promise<Response> =>
  fetchWithAjaxHeader(url)
    .catch((e: string) => {
      throw Error(e);
    })
    .then(errorHandler);

/**
 * fetchの結果としてok以外が返された場合にErrorをスローします。
 *
 * @param url URL
 */
export const fetcher = (url: string) =>
  fetchWithErrorHandling(url).then((res) => res.json());